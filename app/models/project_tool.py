"""ORM model for a tool added to a specific project (spec-020).

No es append-only a propósito (a diferencia de `Finding`/`Report`/`ToolRun`): esto es
configuración de UI (qué tool está agregada a este proyecto y qué acciones tiene permitidas),
no un registro de auditoría -- agregar/quitar/editar es un UPDATE/DELETE normal.

`confirm: bool` (spec-020) fue removido por spec-015, Bloque 3: era el único campo que
anticipaba algo parecido a un gate de confirmación humana antes de ejecutar un comando, pero
el mecanismo real de permission modes vive en `Chat.permission_mode` + `ToolRun`
(`app/models/chat.py`, `app/models/tool_run.py`) -- una propiedad de la conversación, no de
la tool por proyecto. Ver `_migrate_drop_project_tool_confirm_if_present` en `app/main.py`
para el detalle de la migración que da de baja la columna física.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectTool(Base):
    __tablename__ = "project_tools"
    __table_args__ = (UniqueConstraint("case_id", "tool_key", name="uq_project_tools_case_tool"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_cases.id"), nullable=False, index=True
    )
    tool_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("tool_catalog_entries.key"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_action_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
