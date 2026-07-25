"""Pydantic schemas for audit cases."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuditCaseStatus = Literal["open", "closed", "archived"]


class AuditCaseCreate(BaseModel):
    """Payload para crear un caso de auditoría."""

    name: str = Field(..., min_length=1, max_length=255)
    status: AuditCaseStatus = "open"


class AuditCaseOut(BaseModel):
    """Representación de salida de un caso de auditoría."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    created_at: datetime
