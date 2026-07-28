"""ORM model for tool execution proposals/runs (spec-015).

Append-only por diseño, mismo espíritu que `Finding`/`Report` (spec-004): no existe ni se
debe agregar ningún `db.delete(...)` sobre esta tabla. A diferencia de `Finding`/`Report`
no hay un mecanismo de "supersede" -- el único "correctivo" tras un estado terminal
(`executed`/`failed`/`rejected`) es una propuesta nueva (`ToolRun` nuevo), nunca reescribir
uno existente hacia atrás en su ciclo de vida.

`command_resuelto` es el `argv` ya resuelto por la allowlist de sandboxing de
security-compliance (Task 9) -- nunca el texto descriptivo de
`ToolCatalogEntry.actions[].command`, que sigue siendo metadata para humanos (ver docstring
de `app/models/tool_catalog_entry.py`). Esta Task (8) modela la persistencia; la lógica que
resuelve/ejecuta el comando real (sandbox, allowlist, límites de recursos) es alcance de la
Task 9/10, no de este módulo.

`permission_mode_snapshot` congela `Chat.permission_mode` vigente al momento del `INSERT` --
no se recalcula ni se sobrescribe si el usuario cambia `Chat.permission_mode` después.
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


class ToolRun(Base):
    """Propuesta/ejecución de un comando real de una tool. Append-only: nunca se borra."""

    __tablename__ = "tool_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    chat_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chats.id"), nullable=False, index=True
    )
    tool_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("tool_catalog_entries.key"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # `argv` real ya resuelto por la allowlist de security-compliance (Task 9/10) -- nunca el
    # texto descriptivo de `ToolCatalogEntry.actions[].command`.
    command_resuelto: Mapped[str] = mapped_column(String, nullable=False)

    # Congela `Chat.permission_mode` al momento del INSERT (status=proposed). Snapshot
    # histórico, nunca una referencia viva -- no se recalcula si `Chat.permission_mode`
    # cambia después.
    permission_mode_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)

    # Taxonomía cerrada validada como Literal en app/schemas/tool_run.py:
    # proposed | approved | rejected | executed | failed.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")

    # human | llm: quién generó la propuesta inicial (triggered_by) o resolvió la aprobación.
    # Fijado siempre server-side (nunca aceptado del cliente).
    triggered_by: Mapped[str] = mapped_column(String(16), nullable=False)

    # Identificador del usuario humano que aprobó/rechazó vía PATCH. Nunca poblado server-side
    # sin una acción PATCH explícita.
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Mutuamente NULL salvo status="failed". code restringido al set cerrado:
    # no_allowlist_entry | timeout | resource_limit_exceeded | nonzero_exit.
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)

    # Solo poblado cuando error_code="nonzero_exit" o status="executed" con exit code 0
    # disponible.
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
