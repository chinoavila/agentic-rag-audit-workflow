"""Pydantic schemas for chats and their messages (spec-020, frontend React migration).

`MessageOut` expone la representación limpia de cada fila (`tool_name`/`tool_input`/
`tool_output`/`report_id`), nunca el `content` wire crudo de las filas `role="tool"` (ver
`app/models/message.py`): ese wire format es un detalle interno de cómo se reconstruye el
historial para `run_agent_turn`, no algo que el frontend necesite parsear.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["user", "assistant", "tool"]

# auto | accept_edit | manual (spec-015). Taxonomía cerrada, default "manual" (el más
# conservador) en la creación de todo `Chat` -- ver `app/models/chat.py`. La única forma de
# que valga "auto" es un PATCH explícito disparado por una acción humana (nunca el LLM, ver
# `app/routers/chats.py::patch_chat`).
PermissionMode = Literal["auto", "accept_edit", "manual"]


class ChatCreate(BaseModel):
    """Payload para crear un chat. `case_id=None` => chat standalone."""

    case_id: str | None = None
    title: str | None = Field(default=None, max_length=255)


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str | None
    title: str | None
    archived: bool
    permission_mode: PermissionMode
    created_at: datetime
    updated_at: datetime


class ChatPatch(BaseModel):
    """Campos mutables de un chat (los mensajes son append-only).

    `archived` es el soft-hide que dispara el botón de borrar del sidebar del frontend: nunca
    hay un DELETE real sobre `Chat` (ver docstring de `app/routers/chats.py`).

    `permission_mode` (spec-015) es exclusivamente mutable por un caller humano vía este
    mismo `PATCH` -- no existe ninguna tool ni endpoint invocable por el LLM que lo mute.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    archived: bool | None = None
    permission_mode: PermissionMode | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    role: ChatRole
    content: str | None
    tool_name: str | None
    tool_input: dict[str, Any] | None
    tool_output: dict[str, Any] | None
    report_id: str | None
    created_at: datetime


class ChatTurnRequest(BaseModel):
    """Payload de `POST /api/chats/{id}/messages`: el mensaje humano que dispara el turno."""

    content: str = Field(..., min_length=1)


class ChatTurnResponse(BaseModel):
    """Resultado de un turno completo, con las filas ya persistidas (para que el frontend no
    tenga que hacer un segundo `GET /messages` solo para obtener los ids nuevos).
    """

    final_text: str
    hit_max_iterations: bool
    messages: list[MessageOut]
