"""Tool `generate_report`, invocable por el LLM, para generar un informe desde una plantilla
ya indexada (spec-012).

Diseño (mismo patrón que `app/tools/create_finding.py`):

1. **Schema explícito** (agentic-tool-use regla 1): `GenerateReportInput` es la única puerta
   de entrada. El LLM completa únicamente `sections` (una entrada por placeholder de prosa
   que decide llenar) -- nunca puede tocar el resto de la plantilla, que llega intacta al
   renderizado (`app/reports/templates.py::render_template` solo reemplaza `{{placeholder}}`,
   nunca reinterpreta el resto del texto).
2. **Rúbricas antes de persistir** (spec-012): `app/reports/rubrics.py::run_rubrics` corre
   completitud + citas válidas + conformidad de formato. Si alguna falla, la tool NO
   persiste nada (ni fila en DB ni blob) y devuelve `{"error", "code": "rubric_failed",
   "rubric_results": {...}}` con el detalle de qué rúbrica falló y por qué -- reutilizable
   para que el LLM reintente en el mismo turno con secciones corregidas.
3. **Human-in-the-loop** (spec-006 aplicado a reportes): un informe que pasa las rúbricas se
   persiste en `status=pending_review`, NUNCA `published` directo. La aprobación humana
   (`PATCH /api/reports/{id}`, mismo contrato que `findings`) es quien lo mueve a
   `published` -- ver `chainlit_ui/chat.py` para las Actions de aprobar/rechazar.
4. **Errores estructurados** (regla 2, spec-003): toda excepción se captura y se traduce a
   `{"error": str, "code": str}`; esta tool nunca deja propagar un stack trace al LLM.
5. **Inmutabilidad** (spec-011): el contenido de un `Report` ya persistido nunca se
   reescribe -- "corregir" un informe es generar uno nuevo y supersederlo vía
   `PATCH /api/reports/{id}` con `superseded_by` (mismo patrón que `Finding`, spec-004).

Fuera de alcance de este slice, documentado a propósito: a diferencia de `create_finding`,
esta tool no implementa idempotencia best-effort ante reintentos exactos del mismo input.
spec-012 no lo exige explícitamente y cada llamada exitosa produce un artefacto (archivo +
fila) nuevo por diseño; si el LLM reintenta tras un timeout, hoy generaría un segundo
`Report` en vez de deduplicar. Cerrar esto es una extensión directa del mismo patrón de
`_content_idempotency_key` de `create_finding.py` si se vuelve un problema real de uso.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.audit_case import AuditCase
from app.models.report import Report
from app.reports.rubrics import run_rubrics
from app.reports.storage import write_report_blob
from app.reports.templates import TemplateNotFoundError, load_template, render_template
from app.schemas.finding import Citation

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class ReportSectionInput(BaseModel):
    """Una sección de prosa que el LLM decide completar, para un placeholder puntual de la
    plantilla. `citations` reusa `Citation` de `app/schemas/finding.py` (mismo contrato de
    grounding que `create_finding.evidence`, spec-001): nunca vacía.
    """

    placeholder: str = Field(
        ...,
        min_length=1,
        description="Nombre del placeholder {{...}} de la plantilla que esta sección completa.",
    )
    narrative: str = Field(
        ..., min_length=1, description="Texto de prosa que reemplaza al placeholder."
    )
    citations: list[Citation] = Field(
        ...,
        min_length=1,
        description="Citas de evidencia {source, page} que sustentan esta narrativa.",
    )


class GenerateReportInput(BaseModel):
    """Input validado de la tool `generate_report`."""

    case_id: str = Field(..., min_length=1, description="Id (uuid4) del AuditCase existente.")
    template_id: str = Field(
        ..., min_length=1, description="Id de una plantilla ya indexada (docs/report_templates/)."
    )
    title: str = Field(..., min_length=1, max_length=255, description="Título del informe.")
    sections: list[ReportSectionInput] = Field(
        ...,
        min_length=1,
        description="Una entrada por cada placeholder de prosa que la plantilla declara.",
    )


# JSON Schema listo para declarar como `input_schema` de la tool ante el LLM.
input_schema: dict[str, Any] = GenerateReportInput.model_json_schema()


# ---------------------------------------------------------------------------
# Salida estructurada
# ---------------------------------------------------------------------------


def _error(message: str, code: str, **extra: Any) -> dict[str, Any]:
    """Shape uniforme de error de tool (agentic-tool-use regla 2 / spec-003)."""
    return {"error": message, "code": code, **extra}


def _report_to_result(report: Report) -> dict[str, Any]:
    return {
        "report_id": report.id,
        "case_id": report.case_id,
        "template_id": report.template_id,
        "title": report.title,
        "status": report.status,
        "blob_path": report.blob_path,
        "rubric_results": report.rubric_results,
        "created_at": report.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# La tool
# ---------------------------------------------------------------------------


def generate_report(tool_input: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
    """Tool invocable por el LLM: genera un informe desde plantilla y lo persiste si pasa
    las rúbricas automáticas (spec-012).

    Args:
        tool_input: dict crudo recibido del LLM, NO validado. Se valida acá contra
            `GenerateReportInput` antes de tocar cualquier lógica de negocio (regla 1).
        db: sesión de SQLAlchemy opcional (para tests / reuso de una sesión existente). Si
            no se pasa, la tool abre y cierra su propia sesión vía `SessionLocal()`.

    Returns:
        Éxito: dict con `report_id`, `status` (siempre `pending_review`), `blob_path`,
        `rubric_results`, etc.
        Rúbrica fallida (nada se persiste): `{"error", "code": "rubric_failed",
        "rubric_results": {...}}`.
        Error: `{"error": str, "code": str}` -- nunca una excepción cruda (regla 2).
        Códigos posibles: `invalid_input`, `audit_case_not_found`, `template_not_found`,
        `rubric_failed`, `internal_error`.
    """
    try:
        try:
            parsed = GenerateReportInput.model_validate(tool_input)
        except ValidationError as exc:
            return _error(f"Input inválido para generate_report: {exc}", "invalid_input")

        owns_session = db is None
        session = db or SessionLocal()
        try:
            case = session.get(AuditCase, parsed.case_id)
            if case is None:
                return _error(
                    f"Audit case no encontrado: {parsed.case_id}", "audit_case_not_found"
                )

            try:
                template_text = load_template(parsed.template_id)
            except TemplateNotFoundError as exc:
                return _error(str(exc), "template_not_found")

            sections_payload = [
                {
                    "placeholder": s.placeholder,
                    "narrative": s.narrative,
                    "citations": [c.model_dump() for c in s.citations],
                }
                for s in parsed.sections
            ]
            narrative_by_placeholder = {s["placeholder"]: s["narrative"] for s in sections_payload}
            rendered_text = render_template(template_text, narrative_by_placeholder)

            rubric_result = run_rubrics(
                db=session,
                case_id=parsed.case_id,
                template_text=template_text,
                rendered_text=rendered_text,
                sections=sections_payload,
            )
            if not rubric_result.passed:
                return _error(
                    "El borrador no pasó las rúbricas automáticas; no se persistió ningún "
                    "informe. Corregí las secciones señaladas en rubric_results y reintentá.",
                    "rubric_failed",
                    rubric_results=rubric_result.to_dict(),
                )

            report = Report(
                case_id=parsed.case_id,
                template_id=parsed.template_id,
                title=parsed.title,
                status="pending_review",
                blob_path="",  # se completa abajo: hace falta el id, recién disponible tras flush()
                sections=sections_payload,
                rubric_results=rubric_result.to_dict(),
            )
            session.add(report)
            session.flush()  # asigna report.id (default Python-side) sin cerrar la transacción

            report.blob_path = write_report_blob(report.id, rendered_text)
            session.commit()
            session.refresh(report)

            return _report_to_result(report)
        finally:
            if owns_session:
                session.close()
    except Exception as exc:  # noqa: BLE001 - red de seguridad final (spec-003 regla 2)
        return _error(f"Error inesperado generando el informe: {exc}", "internal_error")
