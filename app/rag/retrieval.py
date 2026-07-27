"""Retrieval sobre la colección de documentos de auditoría (spec-001, spec-008).

Contrato de salida — IMPORTANTE para quien consuma esto (`agentic-core`):
`retrieve(...)` devuelve un `RetrievalResult` con datos ESTRUCTURADOS
(`RetrievedChunk` por chunk), nunca un string ya armado "listo para pegar en
el prompt". Esto es deliberado: el texto de cada chunk es contenido de
documentos ingeridos, es decir DATO no confiable, nunca instrucción
(`.ai/skills/security-prompt-injection/SKILL.md` regla 1, spec-005). Quien
ensambla el prompt del LLM (`agentic-core`) debe insertar `RetrievedChunk.text`
dentro de un bloque delimitado y etiquetado explícitamente como no confiable,
por ejemplo:

    <untrusted_context>
    {chunk.text}
    </untrusted_context>

nunca concatenado al system prompt ni interpretado como una instrucción. Este
módulo no implementa ese ensamblado (es responsabilidad de `agentic-core`);
solo se asegura de no devolver nada en un formato que invite a hacerlo mal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from app.rag.vectorstore import get_collection

if TYPE_CHECKING:  # pragma: no cover - solo type hints, ver app/rag/vectorstore.py
    from chromadb.api.models.Collection import Collection

# top_k explícito y acotado (rag-retrieval SKILL.md regla 3): nunca "traer
# todo". El guardrail (`.ai/guardrails/restricted-ops.json`) dispara una
# advertencia si se sube top_k a >=30; ver también TOP_K_WARN_THRESHOLD abajo.
TOP_K = 5
TOP_K_WARN_THRESHOLD = 30

# Umbral mínimo de similitud (spec-008). La colección se crea con
# `hnsw:space: cosine` (ver app/rag/vectorstore.py), por lo que
# `collection.query(...)` devuelve *distancia* coseno y `similarity` acá se
# calcula como `1 - distance` (rango ~[-1, 1], en la práctica [0, 1] para estos
# embeddings). 0.3 es un piso conservador para este slice inicial: bajarlo
# dispara la advertencia del guardrail (ver restricted-ops.json,
# `blocked_soft_warning`, patrón sobre `similarity_threshold`).
SIMILARITY_THRESHOLD = 0.3


@dataclass(frozen=True)
class RetrievedChunk:
    """Un chunk recuperado, con su cita (`source` + `page`) y su score."""

    chunk_id: str
    text: str
    source: str
    page: int
    doc_hash: str
    similarity: float


@dataclass(frozen=True)
class RetrievalResult:
    """Resultado de una consulta de retrieval.

    `insufficient_evidence=True` (spec-008) significa: el mejor resultado no
    superó `SIMILARITY_THRESHOLD`. En ese caso `chunks` está vacío a propósito
    — quien consuma esto debe responder "no hay evidencia suficiente" en vez
    de alucinar con chunks poco relevantes.
    """

    query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    insufficient_evidence: bool = False


# Firma de un futuro reranker: recibe la query y los candidatos crudos del
# vector store, devuelve la lista reordenada (y opcionalmente recortada). No
# se implementa en este slice (no hay ese requisito todavía), pero `retrieve()`
# ya reserva el punto de inserción para no romper el contrato de salida cuando
# se agregue (`.ai/skills/rag-retrieval/SKILL.md` regla 4: las citas deben
# seguir el orden post-rerank).
Reranker = Callable[[str, list[RetrievedChunk]], list[RetrievedChunk]]


def retrieve(
    query: str,
    top_k: int = TOP_K,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    collection: Collection | None = None,
    reranker: Reranker | None = None,
    case_id: str | None = None,
) -> RetrievalResult:
    """Recupera hasta `top_k` chunks relevantes para `query`.

    Si el mejor score no alcanza `similarity_threshold`, devuelve
    `insufficient_evidence=True` y `chunks=[]` (spec-008) en vez de devolver
    resultados de baja relevancia que podrían inducir una respuesta
    alucinada.

    `case_id` (spec-020, best-effort, NO es aislamiento estricto): si se pasa, además de la
    query sin filtro de siempre (que ya devuelve cualquier chunk relevante, sea del corpus
    `global` o de CUALQUIER proyecto -- nunca tuvo aislamiento por caso, esto no lo empeora),
    se corre una segunda query filtrada `where={"case_id": case_id}` para asegurar que la
    evidencia propia de ESTE proyecto aparezca aunque no rankee en el top_k de la query
    general. Los candidatos de ambas queries se mergean por `chunk_id` (sin duplicar) antes de
    aplicar el umbral/top_k. Limitación conocida, documentada a propósito: esto NO evita que
    la query sin filtro traiga chunks de OTRO proyecto si rankean alto -- un aislamiento
    estricto requeriría re-taggear con `case_id="global"` el corpus ya ingerido antes de que
    este campo existiera (fuera de alcance de este slice) o una colección de Chroma separada
    por caso.
    """
    if not query or not query.strip():
        raise ValueError("query no puede ser vacío")
    if top_k >= TOP_K_WARN_THRESHOLD:
        # Defensa en runtime además del guardrail estático: top_k alto == traer
        # de más y diluir la relevancia (rag-retrieval SKILL.md regla 3).
        import warnings

        warnings.warn(
            f"top_k={top_k} >= {TOP_K_WARN_THRESHOLD}: riesgo de contexto irrelevante "
            f"(ver spec-008). Revisar antes de usar en producción.",
            stacklevel=2,
        )

    collection = collection or get_collection()

    def _query(where: dict | None) -> list[RetrievedChunk]:
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            kwargs["where"] = where
        raw = collection.query(**kwargs)
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                text=doc_text,
                source=meta["source"],
                page=meta["page"],
                doc_hash=meta["doc_hash"],
                similarity=1.0 - distance,
            )
            for chunk_id, doc_text, meta, distance in zip(ids, documents, metadatas, distances)
        ]

    candidates = _query(where=None)
    if case_id is not None:
        # Ver docstring de arriba: best-effort, no aislamiento estricto. Mergea por chunk_id
        # para no duplicar un chunk que ya haya salido en la query sin filtro.
        seen_ids = {c.chunk_id for c in candidates}
        for chunk in _query(where={"case_id": case_id}):
            if chunk.chunk_id not in seen_ids:
                candidates.append(chunk)
                seen_ids.add(chunk.chunk_id)
        candidates.sort(key=lambda c: c.similarity, reverse=True)
        candidates = candidates[:top_k]

    # Punto de inserción para reranking futuro: se aplica sobre los candidatos
    # crudos del vector store, antes del filtro de umbral, para que el orden
    # final citado ya sea el post-rerank.
    if reranker is not None:
        candidates = reranker(query, candidates)

    if not candidates or candidates[0].similarity < similarity_threshold:
        return RetrievalResult(query=query, chunks=[], insufficient_evidence=True)

    relevant = [c for c in candidates if c.similarity >= similarity_threshold]
    return RetrievalResult(query=query, chunks=relevant, insufficient_evidence=False)
