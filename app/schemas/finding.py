"""Pydantic schemas for audit findings.

Fuente de verdad de la taxonomía cerrada (`.ai/skills/audit-domain-rules/SKILL.md` regla 1)
y de la regla de evidencia obligatoria (regla 2). `audit-tools` y `agentic-core` deben
importar `Severity`/`FindingStatus`/`Citation` de este módulo en vez de redefinir sus
propios `Literal`/dataclasses equivalentes.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high", "critical"]
FindingStatus = Literal["draft", "pending_review", "final", "rejected"]

HIGH_RISK_SEVERITIES: tuple[str, ...] = ("high", "critical")


class Citation(BaseModel):
    """Una cita de evidencia: fuente + página dentro del documento ingerido."""

    source: str = Field(..., min_length=1)
    page: int | None = Field(default=None, ge=1)


class FindingCreate(BaseModel):
    """Payload para crear un hallazgo.

    `status` no es aceptado en la creación: todo hallazgo nuevo empieza en `draft` (si es
    `low`/`medium`) o `pending_review` (si es `high`/`critical`, ver spec-006) — nunca en
    `final` directo. Esa derivación la hace el router, no el cliente.
    """

    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    severity: Severity
    evidence: list[Citation] = Field(..., min_length=1)
    risk_score: float = Field(
        ...,
        ge=0.0,
        description=(
            "Calculado por una función pura y documentada (ver "
            "audit-domain-rules regla 6, `calculate_risk_score` en audit-tools). "
            "backend-api solo lo persiste, no lo recalcula."
        ),
    )

    @field_validator("evidence")
    @classmethod
    def evidence_not_empty(cls, v: list[Citation]) -> list[Citation]:
        if not v:
            raise ValueError("evidence no puede ser una lista vacía (spec-001)")
        return v


class FindingOut(BaseModel):
    """Representación de salida de un hallazgo."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    title: str
    description: str
    severity: Severity
    evidence: list[Citation]
    risk_score: float
    status: FindingStatus
    approved_by: str | None
    approved_at: datetime | None
    superseded_by: str | None
    created_at: datetime
    updated_at: datetime


class FindingSupersede(BaseModel):
    """Payload mínimo para el caso de uso de soft-supersede (spec-004).

    Marca el hallazgo actual como reemplazado por `superseded_by` sin borrar el registro
    original. Equivalente semántico al único "delete" permitido sobre `Finding`.
    """

    superseded_by: str = Field(..., min_length=1)


class FindingPatch(BaseModel):
    """Payload general para `PATCH /api/findings/{id}`.

    Únicamente permite mover el hallazgo dentro de su ciclo de vida (`status`,
    `approved_by`) o marcarlo como reemplazado (`superseded_by`, ver `FindingSupersede`).
    Nunca acepta `title`/`description`/`evidence`/`severity`: el contenido de un hallazgo
    ya creado es inmutable (solo se reemplaza vía `superseded_by`, spec-004).
    """

    model_config = ConfigDict(extra="forbid")

    status: FindingStatus | None = None
    approved_by: str | None = None
    superseded_by: str | None = None
