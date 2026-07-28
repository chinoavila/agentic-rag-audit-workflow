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

Actualización (Task 10, spec-015): se agrega `params_json` respecto del slice de Task 8. Motivo:
`app/agentic_core/tool_execution/sandbox.py::execute` (Task 9) tiene como ÚNICA firma
`execute(tool_key, action_id, params)` -- nunca acepta un `argv`/comando ya armado como string.
Para poder invocar el sandbox real en el momento de la aprobación/ejecución (Task 10) sin
reconstruir `argv` parseando el texto libre de `command_resuelto` (posiblemente editado por un
humano vía `PATCH`, lo que violaría spec-015 punto 1 -- "nunca se sustituye texto libre no
validado en una posición del argv"), este módulo persiste también los parámetros estructurados
originales (`dict[str, str]`, mismo shape que `AllowlistEntry.resolve_argv`) serializados como
JSON. `command_resuelto` sigue siendo el campo que se muestra a humanos (nunca se usa para
construir el `argv` real); `params_json` es lo único que efectivamente re-alimenta al sandbox
en `app/services/tool_run_execution.py::execute_tool_run`.
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
    # texto descriptivo de `ToolCatalogEntry.actions[].command`. Exclusivamente para mostrar a
    # humanos/auditoría: la ejecución real SIEMPRE re-resuelve el `argv` desde
    # `(tool_key, action_id, params_json)` vía la allowlist -- nunca parsea este string (ver
    # docstring del módulo).
    command_resuelto: Mapped[str] = mapped_column(String, nullable=False)

    # JSON de los parámetros estructurados (`dict[str, str]`) con los que se propuso el
    # comando -- insumo real de `sandbox.execute(tool_key, action_id, params)` en el momento de
    # aprobar/ejecutar (Task 10). `None`/`"{}"` si la acción no admite parámetros variables.
    params_json: Mapped[str | None] = mapped_column(String, nullable=True)

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
