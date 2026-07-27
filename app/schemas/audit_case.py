"""Pydantic schemas for audit cases."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuditCaseStatus = Literal["open", "closed", "archived"]


class AuditCaseCreate(BaseModel):
    """Payload para crear un caso de auditoría (proyecto, frontend React)."""

    name: str = Field(..., min_length=1, max_length=255)
    status: AuditCaseStatus = "open"
    context: str | None = None


class AuditCaseOut(BaseModel):
    """Representación de salida de un caso de auditoría."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    context: str | None
    created_at: datetime


class AuditCasePatch(BaseModel):
    """Único mecanismo de edición de un proyecto ya creado: nombre y/o contexto.

    `status` no se edita acá a propósito (spec-004 territory: cerrar/archivar un caso es una
    transición de negocio, no un campo de formulario libre) -- se agrega cuando haga falta.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    context: str | None = None
