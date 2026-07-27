"""ORM model for audit cases.

Un `AuditCase` agrupa hallazgos (`Finding`); un hallazgo pertenece a exactamente un caso
(ver `.ai/skills/audit-domain-rules/SKILL.md`).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditCase(Base):
    """Caso de auditoría. `created_at` es inmutable: nunca se toca en un UPDATE."""

    __tablename__ = "audit_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    # Contexto/instrucciones libres para el asistente en todos los chats de este proyecto
    # (frontend React, spec-020). Columna agregada después del lanzamiento inicial -- ver
    # `app/main.py::_migrate_add_context_if_missing` para volúmenes `sqlite_data` viejos.
    context: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    findings: Mapped[list["Finding"]] = relationship(  # noqa: F821
        "Finding", back_populates="case", cascade="save-update, merge"
    )
