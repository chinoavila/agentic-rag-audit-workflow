"""Pydantic schemas for the global tool catalog (spec-020)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolActionSchema(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)


class ToolCatalogEntryCreate(BaseModel):
    """Alta de una entry nueva del catálogo. `key` es opcional -- se autogenera de `label` si
    se omite. `actions[].command` es texto descriptivo (ver docstring de
    `app/models/tool_catalog_entry.py`): nunca se ejecuta, no confundir con una tool con
    ejecutor real (`TOOL_DISPATCH`).
    """

    key: str | None = Field(default=None, max_length=64)
    label: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    actions: list[ToolActionSchema] = Field(default_factory=list)


class ToolCatalogEntryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    installed: bool | None = None
    actions: list[ToolActionSchema] | None = None


class ToolCatalogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    description: str
    installed: bool
    actions: list[ToolActionSchema]
    created_at: datetime
