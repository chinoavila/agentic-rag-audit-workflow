"""ORM model for audit findings.

Append-only por diseño (spec-004): no existe ni se debe agregar ningún `db.delete(...)`
sobre esta tabla. El único mecanismo de "borrado" es `superseded_by`, que apunta al id
del `Finding` que reemplaza al actual, dejando el registro original intacto.

La taxonomía de `severity` y `status` se guarda como `String` a nivel de columna (SQLite
no tiene un tipo ENUM nativo cómodo para migraciones), pero se valida como `Literal` a
nivel de Pydantic (`app/schemas/finding.py`) y se re-valida a nivel de aplicación en el
router antes de cualquier escritura. `audit-tools` y `agentic-core` deben reusar esos
mismos `Literal` en vez de aceptar `severity`/`status` libres.

`triggered_by` (spec-005, hallazgo B de security-compliance) distingue si el hallazgo lo
creó un humano (`POST /api/findings`, ver `app/routers/findings.py`) o el LLM (tool
`create_finding`, ver `app/tools/create_finding.py`). Siempre se fija server-side; nunca
se acepta como input del cliente (no existe en `FindingCreate`, solo en `FindingOut`).

NOTA schema: esta app no tiene Alembic, usa `Base.metadata.create_all()` en el startup
(no altera tablas existentes). Si tenés una DB SQLite del slice anterior sin esta columna,
`create_all()` no la va a agregar sola y los INSERT van a fallar contra la tabla vieja —
borrá el volumen y recreá la DB: `docker compose down` + `docker volume rm
agentic-rag-audit-workflow_sqlite_data` (es un prototipo de dev local, no hay datos
productivos que proteger todavía).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Finding(Base):
    """Hallazgo de auditoría. Append-only: nunca se borra, solo se supersede."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_cases.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    # Taxonomía cerrada validada en Pydantic: low | medium | high | critical.
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    # human | llm. Fijado siempre server-side (nunca por el cliente, ver docstring de módulo).
    # server_default evita romper un `create_all()` sobre una tabla ya existente con filas
    # (aunque para una tabla vieja que directamente no tiene la columna, no alcanza: hace
    # falta recrear la DB, ver nota arriba).
    triggered_by: Mapped[str] = mapped_column(String(16), nullable=False, server_default="human")

    # Lista de citas [{"source": str, "page": int}, ...]. Nunca vacía (validado en Pydantic).
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False)

    # draft | pending_review | final | rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft-supersede: apunta al Finding.id que reemplaza a este registro.
    superseded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("findings.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    case = relationship("AuditCase", back_populates="findings")
