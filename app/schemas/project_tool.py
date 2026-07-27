"""Pydantic schemas for a tool added to a project (spec-020)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectToolCreate(BaseModel):
    tool_key: str = Field(..., min_length=1)


class ProjectToolPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    confirm: bool | None = None
    allowed_action_ids: list[str] | None = None


class ProjectToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    tool_key: str
    enabled: bool
    confirm: bool
    allowed_action_ids: list[str]
    created_at: datetime
