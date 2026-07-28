"""Pydantic schemas for `ToolRun` (spec-015).

`ToolRun` documenta cada propuesta/ejecución de un comando real de una tool, gateada por
`Chat.permission_mode` (ver `app/schemas/chat.py::PermissionMode`). Esta Task (8) modela
persistencia y endpoints de transición de estado (`PATCH`/`GET`); la creación de un `ToolRun`
en `status=proposed` y la ejecución real en el sandbox son alcance de agentic-core/Task 9-10
(loop del agente), no de este módulo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ToolRunStatus = Literal["proposed", "approved", "rejected", "executed", "failed"]
TriggeredBy = Literal["human", "llm"]
ToolRunErrorCode = Literal["no_allowlist_entry", "timeout", "resource_limit_exceeded", "nonzero_exit"]

# Transiciones válidas desde `status=proposed` vía PATCH humano (ver
# app/routers/tool_runs.py::patch_tool_run). Cualquier otro `status` de origen, o un `status`
# de destino fuera de este set, se rechaza con 4xx (spec-010).
VALID_TOOL_RUN_PATCH_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"approved", "rejected"},
}


class ToolRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    tool_key: str
    action_id: str
    command_resuelto: str
    permission_mode_snapshot: str
    status: ToolRunStatus
    triggered_by: TriggeredBy
    resolved_by: str | None
    error_code: ToolRunErrorCode | None
    error_detail: str | None
    exit_code: int | None
    created_at: datetime
    updated_at: datetime


class ToolRunPatch(BaseModel):
    """Payload de `PATCH /api/tool-runs/{id}` (solo callable por un humano, nunca por el LLM).

    `status` solo admite `approved`/`rejected` -- son las únicas transiciones que un caller
    humano puede disparar explícitamente vía este endpoint (ver
    `VALID_TOOL_RUN_PATCH_TRANSITIONS`).
    Las transiciones hacia `executed`/`failed` las escribe el ejecutor real del sandbox
    (Task 9/10), no este payload.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    command_resuelto: str | None = Field(default=None, min_length=1)
