"""Pydantic schemas for generated audit reports (spec-011, spec-012).

`ReportSectionOut`/`RubricCheckOut` describen la forma de las columnas JSON de `Report`
(`sections`/`rubric_results`) para que `ReportOut` las tipe en vez de exponerlas como
`dict`/`list` sin validar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.finding import Citation

ReportStatus = Literal["pending_review", "published", "rejected"]


class ReportSectionOut(BaseModel):
    """Una sección de prosa ya persistida, con las citas que la sustentan."""

    placeholder: str
    narrative: str
    citations: list[Citation]


class RubricCheckOut(BaseModel):
    """Resultado de un check individual de rúbrica (spec-012)."""

    name: str
    passed: bool
    detail: str


class ReportOut(BaseModel):
    """Representación de salida de un informe generado."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    template_id: str
    title: str
    status: ReportStatus
    blob_path: str
    sections: list[ReportSectionOut]
    rubric_results: dict
    approved_by: str | None
    approved_at: datetime | None
    superseded_by: str | None
    created_at: datetime
    updated_at: datetime


class ReportPatch(BaseModel):
    """Payload para `PATCH /api/reports/{id}`.

    Única forma de mutar un reporte tras su creación (spec-011): transición de status
    (aprobar/rechazar, spec-006 aplicado a reportes) y/o marcarlo como reemplazado
    (`superseded_by`). Nunca acepta `title`/`sections`/`blob_path`: el contenido de un
    informe ya generado es inmutable, solo se reemplaza vía `superseded_by`.
    """

    model_config = ConfigDict(extra="forbid")

    status: ReportStatus | None = None
    approved_by: str | None = None
    superseded_by: str | None = None
