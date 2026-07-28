"""Índice de documentación de tools + retrieval con scoping de elegibilidad (spec-013, Task 11).

Este módulo es el análogo, para documentación de tools, de `app/rag/vectorstore.py` +
`app/rag/retrieval.py` (documentos de auditoría, spec-001/spec-008): mismo `PersistentClient`/
`persist_dir`, mismo modelo de embeddings, mismo mecanismo de umbral -- pero en una COLECCIÓN
Chroma separada (`TOOL_DOCS_COLLECTION_NAME`, distinta de `COLLECTION_NAME`) y con un paso
adicional, obligatorio y previo al scoring semántico: el filtro estructural de elegibilidad.

Scoping en dos pasos, EN ESTE ORDEN (no invertir, spec-013):

1. Estructural: `app.services.tool_eligibility.list_eligible_tools(db, case_id)` (Task 18,
   única implementación del predicado -- este módulo la consume tal cual, nunca la reimplementa)
   determina el universo de `tool_key` candidatas para `case_id`. Una tool no elegible NUNCA
   entra al paso 2, sin importar cuán relevante sea semánticamente para la query del turno.
2. Semántico: `SIMILARITY_THRESHOLD` (mismo símbolo que `app/rag/retrieval.py`, spec-008 --
   reusado, no redefinido) se aplica ÚNICAMENTE sobre el subconjunto ya elegible del paso 1.

Si ninguna tool elegible supera el umbral, `retrieve_relevant_tools` devuelve
`insufficient_evidence=True` y `tools=[]` -- mismo patrón que `RetrievalResult` en
`app/rag/retrieval.py` (spec-008). Quien consuma esto (Task 12, `agentic-core`, todavía no
implementado) decide, con esa señal, no pasar `tools=` a la API de chat completions en ese
turno (el agente responde sin tool-calling).

Formato de salida (regla 4, `.ai/skills/agentic-tool-use/SKILL.md`): cada tool relevante se
devuelve como `{"name", "description", "input_schema"}` -- el mismo shape interno,
agnóstico de proveedor, que usan `SEARCH_EVIDENCE_TOOL_SPEC`/`CREATE_FINDING_TOOL_SPEC` en
`app/agentic_core/tools_registry.py` antes del adapter `_to_openai_tool`. Directamente usable
para construir el parámetro `tools=` de la API de chat completions; NUNCA texto para
interpolar en el system prompt.

La indexación (`index_tool_catalog`) y el retrieval (`retrieve_relevant_tools`) son funciones
standalone, invocables de forma aislada -- este módulo NO se integra al loop de
`app/agentic_core/loop.py` ni se llama desde el startup de `app/main.py` (esa integración es
Task 12, explícitamente fuera de alcance acá).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.models.tool_catalog_entry import ToolCatalogEntry
from app.rag.retrieval import SIMILARITY_THRESHOLD
from app.rag.vectorstore import EMBEDDING_FUNCTION, EMBEDDING_MODEL_NAME, get_chroma_client
from app.services.tool_eligibility import list_eligible_tools

if TYPE_CHECKING:  # pragma: no cover - solo type hints, ver app/rag/vectorstore.py
    from chromadb import ClientAPI
    from chromadb.api.models.Collection import Collection

# Naming versionado, mismo patrón que `COLLECTION_NAME` en app/rag/vectorstore.py
# (vectorstore-chroma-faiss SKILL.md regla 2), pero con dominio "tool_docs" para que quede en
# una colección Chroma separada de "audit_docs" (spec-013: "vector store separado para
# documentación de tools"). Mismo cliente/persist_dir que la colección documental -- no es un
# mecanismo de persistencia nuevo, solo una colección distinta dentro del mismo store.
TOOL_DOCS_COLLECTION_NAME = f"tool_docs_{EMBEDDING_MODEL_NAME}_v1"

# Tope de tools expuestas por turno, análogo a `TOP_K`/`TOP_K_WARN_THRESHOLD` de
# app/rag/retrieval.py (rag-retrieval SKILL.md regla 3: nunca "traer todo"). Un catálogo de
# tools es, por naturaleza, mucho más chico que un corpus documental -- 10 alcanza sobradamente
# para este slice sin diluir la relevancia de lo que ve el LLM en `tools=`.
TOOL_TOP_K = 10
TOOL_TOP_K_WARN_THRESHOLD = 30


def get_tool_docs_collection(client: ClientAPI | None = None) -> Collection:
    """Obtiene (o crea) la colección Chroma de documentación de tools.

    `hnsw:space: cosine` explícito, igual que `app/rag/vectorstore.py::get_collection` --
    `retrieve_relevant_tools` depende de esa convención para `similarity = 1 - distance`.
    """
    client = client or get_chroma_client()
    return client.get_or_create_collection(
        name=TOOL_DOCS_COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
        metadata={
            "embedding_model": EMBEDDING_MODEL_NAME,
            "domain": "tool_docs",
            "hnsw:space": "cosine",
        },
    )


def _tool_doc_text(entry: ToolCatalogEntry) -> str:
    """Texto a embeber para una `ToolCatalogEntry`: label + description + sus actions.

    Cada action se documenta como "label: command" -- `command` acá es la descripción textual
    de la acción (ver docstring de `app/models/tool_catalog_entry.py`: nunca algo que se
    ejecute), así que es contenido legítimo para indexar y hacer match semántico contra la
    intención del turno.
    """
    lines = [entry.label, entry.description or ""]
    for action in entry.actions or []:
        if not isinstance(action, dict):
            continue
        label = action.get("label") or action.get("id") or ""
        command = action.get("command") or ""
        if label or command:
            lines.append(f"{label}: {command}".strip(": "))
    return "\n".join(line for line in lines if line).strip()


def index_tool_catalog(db: Session, collection: Collection | None = None) -> int:
    """(Re)indexa el catálogo GLOBAL de tools (`ToolCatalogEntry`, sin scoping por `case_id`
    -- el scoping ocurre en `retrieve_relevant_tools`, no acá) en la colección separada de
    tool-docs.

    Cada entry se indexa con `id=entry.key` -- `collection.upsert` hace que reindexar el mismo
    catálogo sea idempotente (mismo patrón que la ingesta documental, spec-002): una entry que
    cambió su `label`/`description`/`actions` se reemplaza en el mismo id, nunca se duplica; una
    entry borrada del catálogo (`db.query(ToolCatalogEntry)` ya no la trae) queda huérfana en el
    índice hasta la próxima reconciliación explícita -- fuera de alcance de este slice (el
    catálogo de tools no tiene, hoy, un endpoint DELETE).

    Devuelve la cantidad de entries indexadas.
    """
    collection = collection or get_tool_docs_collection()
    entries = db.query(ToolCatalogEntry).order_by(ToolCatalogEntry.created_at.asc()).all()
    if not entries:
        return 0

    ids = [entry.key for entry in entries]
    documents = [_tool_doc_text(entry) for entry in entries]
    metadatas = [{"tool_key": entry.key, "label": entry.label} for entry in entries]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(entries)


def _build_input_schema(entry: ToolCatalogEntry) -> dict[str, Any] | None:
    """Deriva un `input_schema` genérico a partir de `entry.actions` (JSON metadata-only, ver
    `app/models/tool_catalog_entry.py`: no trae un schema formal propio). Si la entry no tiene
    actions declaradas, no hay schema que declarar (`input_schema` es "si aplica" -- ver
    docstring del módulo).
    """
    action_ids = [
        action.get("id")
        for action in (entry.actions or [])
        if isinstance(action, dict) and action.get("id")
    ]
    if not action_ids:
        return None
    return {
        "type": "object",
        "properties": {
            "action_id": {
                "type": "string",
                "enum": action_ids,
                "description": f"Acción a ejecutar dentro de la tool '{entry.key}'.",
            },
            "params": {
                "type": "object",
                "description": "Parámetros adicionales para la acción elegida (si aplica).",
            },
        },
        "required": ["action_id"],
        "additionalProperties": False,
    }


def _to_tool_spec(entry: ToolCatalogEntry) -> dict[str, Any]:
    """Shape interno `{"name", "description", "input_schema"}` (agnóstico de proveedor) --
    mismo contrato que `SEARCH_EVIDENCE_TOOL_SPEC`/`CREATE_FINDING_TOOL_SPEC` en
    `app/agentic_core/tools_registry.py`, directamente usable para construir `tools=` (regla 4,
    `agentic-tool-use`), nunca texto para el system prompt.
    """
    spec: dict[str, Any] = {
        "name": entry.key,
        "description": entry.description or entry.label,
    }
    input_schema = _build_input_schema(entry)
    if input_schema is not None:
        spec["input_schema"] = input_schema
    return spec


@dataclass(frozen=True)
class ToolRetrievalResult:
    """Resultado de `retrieve_relevant_tools`, mismo patrón que `RetrievalResult`
    (`app/rag/retrieval.py`, spec-008).

    `insufficient_evidence=True` (nombre reusado a propósito, mismo significado que en
    `RetrievalResult`: "ninguna tool elegible superó `similarity_threshold`") implica
    `tools=[]` -- quien consuma esto (Task 12) no debe pasar `tools=` a la API en ese turno.
    """

    query: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    insufficient_evidence: bool = False


def retrieve_relevant_tools(
    db: Session,
    case_id: str | None,
    query: str,
    top_k: int = TOOL_TOP_K,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    collection: Collection | None = None,
) -> ToolRetrievalResult:
    """Recupera hasta `top_k` tools relevantes para `query`, con el scoping de dos pasos de
    spec-013, EN ESTE ORDEN:

    1. Elegibilidad estructural (`list_eligible_tools`, Task 18): solo las tools elegibles para
       `case_id` entran al paso 2. Este paso ocurre ANTES de cualquier scoring semántico --
       nunca se calcula similitud sobre una tool no elegible para después descartarla, la
       query a Chroma ya viene acotada por `where={"tool_key": {"$in": [...elegibles...]}}`.
    2. Umbral de relevancia semántica (`SIMILARITY_THRESHOLD`, spec-008, mismo mecanismo que
       `app/rag/retrieval.py::retrieve` -- reusado, no redefinido) aplicado únicamente sobre el
       subconjunto ya elegible.

    Si el catálogo elegible está vacío, o si ninguna tool elegible supera el umbral, devuelve
    `insufficient_evidence=True` y `tools=[]` (spec-008 aplicado a tool-docs).
    """
    if not query or not query.strip():
        raise ValueError("query no puede ser vacío")
    if top_k >= TOOL_TOP_K_WARN_THRESHOLD:
        import warnings

        warnings.warn(
            f"top_k={top_k} >= {TOOL_TOP_K_WARN_THRESHOLD}: riesgo de exponer demasiadas "
            f"tools al LLM en un mismo turno (ver spec-013). Revisar antes de usar en "
            f"producción.",
            stacklevel=2,
        )

    # Paso 1: filtro estructural de elegibilidad (Task 18) -- SOLO este subconjunto puede
    # llegar al paso 2, sin importar relevancia semántica.
    eligible_entries = list_eligible_tools(db, case_id)
    if not eligible_entries:
        return ToolRetrievalResult(query=query, tools=[], insufficient_evidence=True)

    entries_by_key = {entry.key: entry for entry in eligible_entries}
    eligible_keys = sorted(entries_by_key)

    collection = collection or get_tool_docs_collection()
    raw = collection.query(
        query_texts=[query],
        n_results=min(top_k, len(eligible_keys)),
        where={"tool_key": {"$in": eligible_keys}},
        include=["metadatas", "distances"],
    )
    ids = (raw.get("ids") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    # Paso 2: umbral de relevancia semántica (spec-008), aplicado únicamente sobre lo que ya
    # pasó el paso 1 (los ids que vuelven acá son, por construcción del `where` de arriba, un
    # subconjunto de `eligible_keys` -- nunca hace falta re-chequear elegibilidad).
    scored = sorted(
        (
            (tool_key, 1.0 - distance)
            for tool_key, distance in zip(ids, distances)
            if tool_key in entries_by_key
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    relevant = [(key, score) for key, score in scored if score >= similarity_threshold]

    if not relevant:
        return ToolRetrievalResult(query=query, tools=[], insufficient_evidence=True)

    tools = [_to_tool_spec(entries_by_key[key]) for key, _score in relevant[:top_k]]
    return ToolRetrievalResult(query=query, tools=tools, insufficient_evidence=False)
