"""Tests para spec-013: Exposición Dinámica de Tools vía Retrieval.

Cubre `app/rag/tool_docs.py` (Task 11 del plan de permission modes): índice de tool-docs en
una colección Chroma separada de la documental (`app/rag/vectorstore.py`) + retrieval con el
scoping de dos pasos de spec-013 -- primero elegibilidad estructural
(`app/services/tool_eligibility.py`, Task 18), recién después `SIMILARITY_THRESHOLD`
(spec-008, `app/rag/retrieval.py`).

DB de test: `db_session` (fixture de `tests/specs/conftest.py`, sqlite in-memory). Vector
store de tool-docs: `EphemeralClient` local a este archivo (mismo patrón que `chroma_client`/
`test_collection` de `conftest.py`, pero apuntando a la colección de tool-docs en vez de la
documental) -- así un test de este archivo nunca contamina la colección `test_collection` de
otros specs (spec-001/002/008), ni viceversa.
"""

from __future__ import annotations

import chromadb
import pytest
from chromadb.config import Settings

from app.models.audit_case import AuditCase
from app.models.project_tool import ProjectTool
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.rag.tool_docs import (
    TOOL_DOCS_COLLECTION_NAME,
    index_tool_catalog,
    retrieve_relevant_tools,
)
from app.rag.vectorstore import COLLECTION_NAME as AUDIT_DOCS_COLLECTION_NAME
from app.rag.vectorstore import EMBEDDING_FUNCTION


# ---------------------------------------------------------------------------
# Fixtures locales (vector store de tool-docs, distinto del `test_collection` documental de
# conftest.py).
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool_docs_chroma_client():
    """Cliente Chroma in-memory dedicado, con el mismo `reset()` post-test que `chroma_client`
    de `conftest.py` (ver docstring de esa fixture: evita fuga de datos entre tests que
    comparten `COLLECTION_NAME`/`Settings` dentro del mismo proceso de pytest).
    """
    client = chromadb.EphemeralClient(settings=Settings(allow_reset=True))
    yield client
    client.reset()


@pytest.fixture()
def tool_docs_collection(tool_docs_chroma_client):
    """Colección Chroma in-memory de tool-docs, mismo nombre/`embedding_function` que
    `app.rag.tool_docs.get_tool_docs_collection` usaría en runtime real.
    """
    return tool_docs_chroma_client.get_or_create_collection(
        name=TOOL_DOCS_COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
        metadata={
            "embedding_model": "test",
            "domain": "tool_docs",
            "hnsw:space": "cosine",
        },
    )


# ---------------------------------------------------------------------------
# Helpers de setup de DB.
# ---------------------------------------------------------------------------


def _case(db, name: str = "Caso de test") -> AuditCase:
    case = AuditCase(name=name)
    db.add(case)
    db.commit()
    return case


def _catalog_entry(
    db,
    key: str,
    *,
    label: str,
    description: str,
    installed: bool = True,
    actions: list | None = None,
) -> ToolCatalogEntry:
    entry = ToolCatalogEntry(
        key=key,
        label=label,
        description=description,
        installed=installed,
        actions=actions or [],
    )
    db.add(entry)
    db.commit()
    return entry


def _project_tool(db, case_id: str, tool_key: str, *, enabled: bool) -> ProjectTool:
    row = ProjectTool(case_id=case_id, tool_key=tool_key, enabled=enabled, allowed_action_ids=[])
    db.add(row)
    db.commit()
    return row


@pytest.mark.spec_013
class TestExposicionDinamicaToolsRetrieval:
    """Spec-013: Exposición Dinámica de Tools vía Retrieval (.ai/specs/rag/spec-013-exposicion-dinamica-tools-retrieval.md)"""

    def test_tool_docs_indexed_in_separate_vector_store(self, db_session, tool_docs_collection):
        """El índice de tool-docs vive en una colección Chroma DISTINTA de la documental
        (`app/rag/vectorstore.py::COLLECTION_NAME`), mismo mecanismo de persistencia
        (`PersistentClient`/`persist_dir`), no un vector store nuevo.
        """
        _catalog_entry(
            db_session,
            "search_evidence",
            label="Buscar evidencia",
            description="Busca evidencia relevante en los documentos de auditoría indexados.",
        )
        _catalog_entry(
            db_session,
            "generate_report",
            label="Generar reporte",
            description="Genera el informe final de auditoría a partir de los hallazgos.",
        )

        indexed_count = index_tool_catalog(db_session, collection=tool_docs_collection)

        assert indexed_count == 2
        # Colección de tool-docs != colección documental (nombre explícitamente distinto).
        assert TOOL_DOCS_COLLECTION_NAME != AUDIT_DOCS_COLLECTION_NAME
        assert tool_docs_collection.name == TOOL_DOCS_COLLECTION_NAME

        stored = tool_docs_collection.get(include=["metadatas"])
        assert set(stored["ids"]) == {"search_evidence", "generate_report"}
        assert {m["tool_key"] for m in stored["metadatas"]} == {"search_evidence", "generate_report"}

    def test_installed_tool_without_project_tool_row_is_eligible_by_default(
        self, db_session, tool_docs_collection
    ):
        """Caso 1 de spec-013: installed=True, sin fila ProjectTool -> elegible -> aparece en
        el resultado de retrieval si además supera el umbral semántico.
        """
        case = _case(db_session)
        _catalog_entry(
            db_session,
            "search_evidence",
            label="Buscar evidencia",
            description="Busca evidencia relevante en los documentos de auditoría indexados "
            "para una consulta en lenguaje natural sobre papeles de trabajo.",
        )
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="necesito buscar evidencia en los documentos de auditoría",
            collection=tool_docs_collection,
        )

        assert result.insufficient_evidence is False
        assert [t["name"] for t in result.tools] == ["search_evidence"]

    def test_project_tool_enabled_false_excludes_installed_tool_for_that_case(
        self, db_session, tool_docs_collection
    ):
        """Caso 2 de spec-013: installed=True pero ProjectTool.enabled=False para ESE case_id
        -> excluida del retrieval aunque sea semánticamente muy relevante para la query.
        """
        case = _case(db_session)
        _catalog_entry(
            db_session,
            "search_evidence",
            label="Buscar evidencia",
            description="Busca evidencia relevante en los documentos de auditoría indexados "
            "para una consulta en lenguaje natural sobre papeles de trabajo.",
        )
        _project_tool(db_session, case.id, "search_evidence", enabled=False)
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="necesito buscar evidencia en los documentos de auditoría",
            collection=tool_docs_collection,
        )

        assert result.tools == []
        assert result.insufficient_evidence is True

    def test_tool_catalog_installed_false_excludes_tool_even_with_project_tool_enabled_true(
        self, db_session, tool_docs_collection
    ):
        """Caso 3 de spec-013: installed=False manda sobre cualquier override de proyecto --
        ProjectTool.enabled=True no puede "resucitar" una tool desinstalada globalmente.
        """
        case = _case(db_session)
        _catalog_entry(
            db_session,
            "generate_report",
            label="Generar reporte",
            description="Genera el informe final de auditoría a partir de los hallazgos "
            "registrados en este caso.",
            installed=False,
        )
        _project_tool(db_session, case.id, "generate_report", enabled=True)
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="quiero generar el informe final de auditoría",
            collection=tool_docs_collection,
        )

        assert result.tools == []
        assert result.insufficient_evidence is True

    def test_only_eligible_tools_above_threshold_are_exposed_to_llm(
        self, db_session, tool_docs_collection
    ):
        """El scoping de dos pasos completo, en el orden correcto:

        - `search_evidence`: elegible (installed=True, sin override) Y relevante -> expuesta.
        - `generate_report_ineligible`: NO elegible (installed=False) aunque su descripción sea
          semánticamente idéntica a la de `search_evidence` -> nunca debe exponerse, sin
          importar cuán alto puntuaría en el paso semántico si se evaluara.
        - `unrelated_tool`: elegible, pero semánticamente irrelevante para la query (por debajo
          de `SIMILARITY_THRESHOLD`) -> excluida por el paso 2, no por el paso 1.
        """
        case = _case(db_session)
        relevant_description = (
            "Busca evidencia relevante en los documentos de auditoría indexados para una "
            "consulta en lenguaje natural sobre papeles de trabajo."
        )
        _catalog_entry(
            db_session,
            "search_evidence",
            label="Buscar evidencia",
            description=relevant_description,
            installed=True,
        )
        _catalog_entry(
            db_session,
            "generate_report_ineligible",
            label="Buscar evidencia (no instalada)",
            description=relevant_description,
            installed=False,
        )
        _catalog_entry(
            db_session,
            "unrelated_tool",
            label="Recetas de cocina",
            description="Sugiere recetas de cocina italiana y pastas caseras para el almuerzo.",
            installed=True,
        )
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="necesito buscar evidencia en los documentos de auditoría",
            collection=tool_docs_collection,
        )

        tool_names = {t["name"] for t in result.tools}
        assert tool_names == {"search_evidence"}
        assert "generate_report_ineligible" not in tool_names
        assert "unrelated_tool" not in tool_names

    def test_no_relevant_tool_falls_back_to_no_tool_call(self, db_session, tool_docs_collection):
        """Ninguna tool elegible supera el umbral -> `insufficient_evidence=True`, `tools=[]`
        (mismo patrón que `insufficient_evidence` en `app/rag/retrieval.py::retrieve`, spec-008).
        Quien consuma esto (Task 12, agentic-core) decide no pasar `tools=` a la API: el
        agente responde sin tool-calling.
        """
        case = _case(db_session)
        _catalog_entry(
            db_session,
            "unrelated_tool",
            label="Recetas de cocina",
            description="Sugiere recetas de cocina italiana y pastas caseras para el almuerzo.",
            installed=True,
        )
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="necesito buscar evidencia en los documentos de auditoría",
            collection=tool_docs_collection,
        )

        assert result.insufficient_evidence is True
        assert result.tools == []

    def test_tool_declaration_passed_via_tools_param_not_system_prompt(
        self, db_session, tool_docs_collection
    ):
        """La tool recuperada se devuelve como dato estructurado (`{"name", "description",
        "input_schema"}`), directamente usable para construir `tools=` -- nunca como string
        para interpolar en el system prompt (regla 4, `agentic-tool-use`).
        """
        case = _case(db_session)
        _catalog_entry(
            db_session,
            "search_evidence",
            label="Buscar evidencia",
            description="Busca evidencia relevante en los documentos de auditoría indexados "
            "para una consulta en lenguaje natural sobre papeles de trabajo.",
            actions=[
                {"id": "search", "label": "Buscar", "command": "internal:search_evidence"},
            ],
        )
        index_tool_catalog(db_session, collection=tool_docs_collection)

        result = retrieve_relevant_tools(
            db_session,
            case.id,
            query="necesito buscar evidencia en los documentos de auditoría",
            collection=tool_docs_collection,
        )

        assert isinstance(result.tools, list)
        assert len(result.tools) == 1
        tool_spec = result.tools[0]

        # Estructura, no texto: nunca un str listo para pegar en el system prompt.
        assert isinstance(tool_spec, dict)
        assert tool_spec["name"] == "search_evidence"
        assert isinstance(tool_spec["description"], str) and tool_spec["description"]
        assert "input_schema" in tool_spec
        assert tool_spec["input_schema"]["type"] == "object"
        assert "action_id" in tool_spec["input_schema"]["properties"]
        assert tool_spec["input_schema"]["properties"]["action_id"]["enum"] == ["search"]
