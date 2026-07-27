"""ORM model for a file uploaded to a specific audit case/project (spec-020).

Append-only: subir un archivo nunca borra ni reemplaza el anterior (a diferencia de la
ingesta idempotente por `doc_hash` que ya hace `app/rag/ingestion.py` a nivel de vector
store) -- si dos archivos con el mismo nombre se suben dos veces, quedan dos filas `CaseFile`
(dos versiones), igual criterio append-only que `Finding`/`Report`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseFile(Base):
    """Un archivo adjuntado a un proyecto, ya ingerido en el vector store con `case_id` real
    en su metadata de Chroma (ver `app/rag/ingestion.py`) -- buscable junto con la normativa
    general desde `search_evidence` (best-effort, ver `app/rag/retrieval.py`).
    """

    __tablename__ = "case_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_cases.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_path: Mapped[str] = mapped_column(String(512), nullable=False)
    chunks_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
