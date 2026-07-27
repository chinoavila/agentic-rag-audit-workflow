"""Pydantic schemas for files uploaded to an audit case (spec-020)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    filename: str
    size_bytes: int
    chunks_indexed: int
    created_at: datetime
