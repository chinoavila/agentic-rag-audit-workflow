"""Endpoints for files uploaded to an audit case/project (spec-020).

El archivo se guarda a disco (`app/rag/case_file_storage.py`) Y se ingesta en el vector store
tageado con el `case_id` real (`app/rag/ingestion.py`), para que `search_evidence` pueda
encontrarlo (best-effort, ver docstring de `app/rag/retrieval.py::retrieve`) sin ninguna tool
nueva -- mismo criterio de diseño que el plan de migración ya aprobó.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.audit_case import AuditCase
from app.models.case_file import CaseFile
from app.rag.case_file_storage import write_case_file_blob
from app.rag.ingestion import UnsupportedFormatError, compute_doc_hash, ingest_document
from app.rag.vectorstore import get_collection
from app.schemas.case_file import CaseFileOut

router = APIRouter(prefix="/api/audit-cases", tags=["case-files"])


def _get_case_or_404(db: Session, case_id: str) -> AuditCase:
    case = db.get(AuditCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Audit case not found", "audit_case_not_found"
            ),
        )
    return case


@router.post(
    "/{case_id}/files", response_model=CaseFileOut, status_code=status.HTTP_201_CREATED
)
async def upload_case_file(
    case_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CaseFile:
    """Sube un archivo a un proyecto: lo guarda y lo ingesta en Chroma con `case_id` real."""
    _get_case_or_404(db, case_id)

    content = await file.read()
    filename = file.filename or "archivo_sin_nombre"

    case_file = CaseFile(
        case_id=case_id,
        filename=filename,
        size_bytes=len(content),
        doc_hash=compute_doc_hash(content),
        blob_path="",
        chunks_indexed=0,
    )

    # `ingest_document` necesita un path real en disco (extractors PDF/DOCX/XLSX leen del
    # filesystem) -- se escribe a un archivo temporal con la extensión original para que
    # `validate_supported_format` (basada en la extensión) lo acepte.
    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        try:
            result = ingest_document(Path(tmp.name), get_collection(), case_id=case_id)
        except UnsupportedFormatError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_error_detail(status.HTTP_400_BAD_REQUEST, str(exc), "unsupported_format"),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=api_error_detail(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, f"Fallo la ingesta: {exc}", "ingestion_failed"
                ),
            ) from exc

    case_file.chunks_indexed = result.chunks_indexed
    case_file.blob_path = write_case_file_blob(case_id, case_file.id, filename, content)

    db.add(case_file)
    db.commit()
    db.refresh(case_file)
    return case_file


@router.get("/{case_id}/files", response_model=list[CaseFileOut])
def list_case_files(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CaseFile]:
    _get_case_or_404(db, case_id)
    return (
        db.query(CaseFile)
        .filter(CaseFile.case_id == case_id)
        .order_by(CaseFile.created_at.desc())
        .all()
    )
