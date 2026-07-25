"""Router de retrieval RAG.

`POST /api/rag/query`: retrieval de solo lectura sobre la colección de
documentos de auditoría ya indexados.
`POST /api/rag/ingest`: dispara la ingesta (idempotente) de
`docs/sample_evidence/` — ver `app/rag/ingest_sample.py` para la alternativa de
script manual (misma función de ingesta, dos formas de invocarla).

Nota para `agentic-core` (quien consume `/api/rag/query`): la respuesta trae
los chunks como datos estructurados (`chunks[].text`, `.citation`), nunca como
un string pre-armado. Insertar `chunks[].text` en el prompt del LLM dentro de
un bloque `<untrusted_context>...</untrusted_context>` (spec-005) — nunca
concatenado al system prompt. Si `insufficient_evidence=True`, `chunks` viene
vacío a propósito (spec-008): la respuesta al usuario debe declarar
explícitamente que no hay evidencia suficiente, no generar una afirmación de
auditoría igual.

Contrato de error (spec-010): se levantan `HTTPException` con `detail` string
(nunca 200 disfrazado de error); los handlers globales de `app/errors.py`
(registrados por `backend-api` en `app/main.py`) normalizan la respuesta al
shape uniforme `{"detail": ..., "code": ...}` para toda la API, este router
no duplica esa lógica.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.rag.ingestion import IngestionResult, UnsupportedFormatError, ingest_directory
from app.rag.retrieval import RetrievalResult, retrieve

router = APIRouter(prefix="/api/rag", tags=["rag"])

# docs/sample_evidence/ vive en la raíz del repo, tres niveles arriba de este
# archivo (app/routers/rag_retrieval.py -> app/routers -> app -> raíz).
SAMPLE_EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "sample_evidence"


# ---------------------------------------------------------------------------
# Schemas (Pydantic) — locales a este router. No se tocan app/schemas/* para
# evitar pisar el trabajo en paralelo de `backend-api` sobre esa carpeta.
# ---------------------------------------------------------------------------


class RagQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Consulta en lenguaje natural sobre los documentos de auditoría indexados.",
    )


class Citation(BaseModel):
    """Cita mínima spec-001: fuente + página/sección del chunk."""

    source: str
    page: int


class RetrievedChunkOut(BaseModel):
    chunk_id: str
    text: str
    similarity: float
    citation: Citation


class RagQueryResponse(BaseModel):
    query: str
    insufficient_evidence: bool
    chunks: list[RetrievedChunkOut]


class IngestResultOut(BaseModel):
    source: str
    doc_hash: str
    status: str
    chunks_indexed: int


class IngestSampleResponse(BaseModel):
    directory: str
    ingested: list[IngestResultOut]


def _to_response(result: RetrievalResult) -> RagQueryResponse:
    return RagQueryResponse(
        query=result.query,
        insufficient_evidence=result.insufficient_evidence,
        chunks=[
            RetrievedChunkOut(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                similarity=chunk.similarity,
                citation=Citation(source=chunk.source, page=chunk.page),
            )
            for chunk in result.chunks
        ],
    )


def _to_ingest_out(result: IngestionResult) -> IngestResultOut:
    return IngestResultOut(
        source=result.source,
        doc_hash=result.doc_hash,
        status=result.status,
        chunks_indexed=result.chunks_indexed,
    )


@router.post("/query", response_model=RagQueryResponse, status_code=status.HTTP_200_OK)
async def query_rag(payload: RagQueryRequest) -> RagQueryResponse:
    try:
        result = retrieve(query=payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # errores de infraestructura (chroma, io, etc.)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo el retrieval: {exc}",
        ) from exc

    return _to_response(result)


@router.post(
    "/ingest",
    response_model=IngestSampleResponse,
    status_code=status.HTTP_200_OK,
)
async def ingest_sample_evidence() -> IngestSampleResponse:
    """Ingesta idempotente de `docs/sample_evidence/` (endpoint interno/manual).

    Pensado para invocarse a mano (curl/Swagger) durante desarrollo, no para
    ser una tool expuesta al LLM del agente (`agentic-core` decide qué tools
    son invocables por el modelo; ingesta de documentos no es una de ellas en
    este slice).
    """
    if not SAMPLE_EVIDENCE_DIR.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el directorio de evidencia de ejemplo: {SAMPLE_EVIDENCE_DIR}",
        )

    try:
        results = ingest_directory(SAMPLE_EVIDENCE_DIR)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo la ingesta: {exc}",
        ) from exc

    return IngestSampleResponse(
        directory=str(SAMPLE_EVIDENCE_DIR),
        ingested=[_to_ingest_out(r) for r in results],
    )
