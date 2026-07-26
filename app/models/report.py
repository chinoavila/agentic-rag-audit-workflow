"""ORM model for generated audit reports.

Append-only por diseño (spec-011, mismo contrato que `Finding`/spec-004): no existe ni se
debe agregar ningún `db.delete(...)` sobre esta tabla. El único mecanismo de "borrado" es
`superseded_by`, que apunta al id del `Report` que reemplaza al actual, dejando el registro
(y el archivo en `app/reports/storage.py`) original intactos.

`status` nunca es `draft`: un `Report` solo se persiste después de pasar las rúbricas
automáticas de spec-012 (`app/reports/rubrics.py`), y siempre entra en `pending_review` --
la aprobación humana (`PATCH /api/reports/{id}`, mismo contrato que `Finding`/spec-006) es
quien lo mueve a `published`. No hay excepción por severidad como en `Finding`: todo informe
pasa por el gate.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    """Informe de auditoría generado desde plantilla. Append-only: nunca se borra, solo se
    supersede.
    """

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_cases.id"), nullable=False, index=True
    )
    template_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # pending_review | published | rejected.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")

    # Ruta relativa dentro del blob storage local (ver app/reports/storage.py). Nunca se
    # borra el archivo al supersederse (spec-011): sigue accesible vía el id histórico.
    blob_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Secciones que completó el LLM al generar el informe:
    # [{"placeholder": str, "narrative": str, "citations": [{"source": str, "page": int|None}, ...]}, ...]
    # Persistido para poder auditar qué evidencia sustentó cada sección sin reparsear el blob.
    sections: Mapped[list] = mapped_column(JSON, nullable=False)

    # Resultado de la corrida de rúbricas que permitió persistir este informe (spec-012):
    # {"passed": bool, "checks": [{"name": str, "passed": bool, "detail": str}, ...]}.
    rubric_results: Mapped[dict] = mapped_column(JSON, nullable=False)

    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft-supersede: apunta al Report.id que reemplaza a este registro.
    superseded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
