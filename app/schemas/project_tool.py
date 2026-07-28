"""Pydantic schemas for a tool added to a project (spec-020).

`confirm` fue removido (spec-015, Bloque 3): un payload con `confirm` responde 422 vía
`extra="forbid"`, no se ignora silenciosamente. El mecanismo real de confirmación humana
antes de ejecutar un comando es `Chat.permission_mode` + `ToolRun`, ver
`app/schemas/chat.py`/`app/schemas/tool_run.py`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectToolCreate(BaseModel):
    tool_key: str = Field(..., min_length=1)


class ProjectToolPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    allowed_action_ids: list[str] | None = None


class ProjectToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    tool_key: str
    enabled: bool
    allowed_action_ids: list[str]
    created_at: datetime
