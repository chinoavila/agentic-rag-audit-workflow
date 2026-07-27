"""Tool `create_finding`, invocable por el LLM (tool-calling), para registrar un hallazgo.

Diseño (ver `.ai/skills/agentic-tool-use/SKILL.md` y `.ai/skills/audit-domain-rules/SKILL.md`):

1. **Schema explícito** (regla 1 de `agentic-tool-use`): `CreateFindingInput` (Pydantic) es la
   única puerta de entrada. Nunca se acepta un string libre sin parsear; `input_schema`
   (JSON Schema derivado de ese modelo) es lo que `agentic-core` debe declarar al LLM tal
   cual, sin reescribirlo como texto en el system prompt (regla 4).
2. **Persistencia**: en vez de hacer un HTTP call interno al propio backend, esta tool reusa
   directamente la sesión de SQLAlchemy (`app.db.SessionLocal`) y los modelos ORM
   (`app.models.finding.Finding`, `app.models.audit_case.AuditCase`) — es el approach más
   simple para este slice (mismo proceso, sin latencia de red ni necesidad de un cliente
   HTTP interno) y evita duplicar la validación de `FindingCreate` haciendo un segundo salto
   por FastAPI. La regla de derivar `status` inicial a partir de `severity` (spec-006) se
   replica acá de forma mínima usando la misma constante `HIGH_RISK_SEVERITIES` que usa
   `app/routers/findings.py::_initial_status_for_severity`, para no importar un símbolo
   privado de otro módulo de dominio.
3. **Errores estructurados** (regla 2, spec-003): toda excepción se captura y se traduce a
   `{"error": str, "code": str}`. Esta tool nunca deja propagar un stack trace al LLM.
4. **Idempotencia** (regla 6): ver `_content_idempotency_key` más abajo.
5. **Salida estructurada** (regla 5): éxito siempre es un `dict` JSON-serializable con
   `finding_id`, `severity`, `evidence`, `risk_score`, `status`, etc. — nunca prosa libre.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.audit_case import AuditCase
from app.models.finding import Finding
from app.schemas.finding import HIGH_RISK_SEVERITIES, Citation, Severity

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class CreateFindingInput(BaseModel):
    """Input validado de la tool `create_finding`.

    Reusa `Severity`/`Citation` de `app/schemas/finding.py` (fuente de verdad de la
    taxonomía cerrada y de la regla "evidencia obligatoria") en vez de redefinir tipos
    equivalentes, tal como indica el docstring de ese módulo.
    """

    case_id: str = Field(
        ...,
        min_length=1,
        description="Id (uuid4) del AuditCase existente al que pertenece el hallazgo.",
    )
    title: str = Field(..., min_length=1, max_length=255, description="Título corto del hallazgo.")
    description: str = Field(..., min_length=1, description="Descripción detallada del hallazgo.")
    severity: Severity = Field(
        ...,
        description="Taxonomía cerrada: low | medium | high | critical. Nunca un string libre.",
    )
    evidence: list[Citation] = Field(
        ...,
        min_length=1,
        description="Lista no vacía de citas {source, page} que sustentan el hallazgo.",
    )
    idempotency_key: str | None = Field(
        default=None,
        description=(
            "Opcional. Clave provista por el agente para deduplicar reintentos explícitos "
            "dentro del mismo proceso. Si se omite, la tool deriva una clave de contenido "
            "determinista a partir de case_id+title+evidence (ver docstring de "
            "`_content_idempotency_key`)."
        ),
    )


# JSON Schema listo para declarar como `input_schema` de la tool ante el LLM
# (`agentic-core` debe importar esto directo, nunca reescribirlo como texto).
#
# `case_id` se quita de lo que el LLM ve y puede completar (spec-020): el LLM no tiene forma
# confiable de conocer el uuid real del `Chat.case_id` en el que está, y dejarlo como campo
# libre lo empuja a inventar un id (`"caso_001"`, etc.) que nunca existe. `agentic_core.loop`
# threadea el `case_id` real desde `run_agent_turn` y `_dispatch_create_finding`
# (`tools_registry.py`) lo inyecta en `tool_input` antes de validar -- mismo criterio de
# "identidad/scope nunca viene del LLM" que ya aplica `triggered_by`/`approved_by` en esta
# misma tool. `CreateFindingInput.case_id` sigue siendo un campo real y requerido: se sigue
# validando tal cual, solo deja de estar en el schema que ve el LLM.
input_schema: dict[str, Any] = CreateFindingInput.model_json_schema()
input_schema["properties"].pop("case_id", None)
if "case_id" in input_schema.get("required", []):
    input_schema["required"].remove("case_id")


# ---------------------------------------------------------------------------
# calculate_risk_score: función pura y documentada (audit-domain-rules regla 6)
# ---------------------------------------------------------------------------

# Puntaje base por severidad sobre una escala 0-10, en cuartiles: low=2.5, medium=5.0,
# high=7.5, critical=10.0. Es la fuente dominante del score: la severidad es el proxy
# principal de impacto/riesgo de un hallazgo de auditoría.
SEVERITY_BASE_SCORE: dict[str, float] = {
    "low": 2.5,
    "medium": 5.0,
    "high": 7.5,
    "critical": 10.0,
}

# Bonus por evidencia: cada cita adicional (más allá de la primera, que ya es obligatoria)
# suma un pequeño incremento. La idea NO es que "más evidencia = más severo", sino que un
# hallazgo respaldado por múltiples fuentes independientes está mejor corroborado y merece
# priorizarse levemente por sobre uno equivalente con una sola cita, dentro del mismo tramo
# de severidad. Se cappea para que la evidencia nunca pueda empujar un hallazgo `low` por
# encima de uno `medium`/`high`/`critical` sin evidencia extra.
EVIDENCE_BONUS_PER_EXTRA_CITATION = 0.5
EVIDENCE_BONUS_CAP = 1.5  # tope: como mucho 3 citas extra cuentan (3 * 0.5 = 1.5)

MAX_RISK_SCORE = 10.0
MIN_RISK_SCORE = 0.0


def calculate_risk_score(severity: Severity, evidence_count: int) -> float:
    """Calcula el `risk_score` (0.0-10.0) de un hallazgo de forma pura y determinista.

    Fórmula: `risk_score = min(SEVERITY_BASE_SCORE[severity] + evidence_bonus, 10.0)`, donde
    `evidence_bonus = min((evidence_count - 1) * 0.5, 1.5)`. Ver comentarios de
    `SEVERITY_BASE_SCORE`/`EVIDENCE_BONUS_*` arriba para la justificación de cada constante.

    Args:
        severity: una de `low|medium|high|critical` (taxonomía cerrada de
            `app.schemas.finding.Severity`).
        evidence_count: cantidad de citas de evidencia del hallazgo (debe ser >= 1; todo
            hallazgo requiere al menos una cita, spec-001).

    Returns:
        Un float en el rango [0.0, 10.0], redondeado a 2 decimales.

    Raises:
        ValueError: si `severity` no es una de las 4 taxonomías válidas, o si
            `evidence_count < 1`.
    """
    if severity not in SEVERITY_BASE_SCORE:
        raise ValueError(
            f"severity inválida: {severity!r} (debe ser una de {sorted(SEVERITY_BASE_SCORE)})"
        )
    if evidence_count < 1:
        raise ValueError(
            "evidence_count debe ser >= 1: todo hallazgo requiere evidencia (spec-001)"
        )

    base = SEVERITY_BASE_SCORE[severity]
    evidence_bonus = min(
        (evidence_count - 1) * EVIDENCE_BONUS_PER_EXTRA_CITATION, EVIDENCE_BONUS_CAP
    )
    return round(min(max(base + evidence_bonus, MIN_RISK_SCORE), MAX_RISK_SCORE), 2)


# ---------------------------------------------------------------------------
# Idempotencia (agentic-tool-use regla 6 / spec-003)
# ---------------------------------------------------------------------------

# Cache en memoria de proceso: idempotency_key explícita -> finding_id ya creado.
# Es un mecanismo *best-effort* (se pierde al reiniciar el proceso o en despliegues
# multi-worker) que complementa, pero no reemplaza, la verificación por contenido de
# `_content_idempotency_key` (esa sí sobrevive reinicios porque se recalcula contra lo
# persistido en DB). Si en el futuro se necesita una garantía de idempotencia persistida
# y multi-proceso, eso requiere una columna/constraint única en `Finding` -> escalar a
# `backend-api`.
_EXPLICIT_IDEMPOTENCY_CACHE: dict[str, str] = {}


def _content_idempotency_key(case_id: str, title: str, evidence: list[dict]) -> str:
    """Deriva una clave determinista de deduplicación a partir de (case_id, title, evidence).

    Se eligió `case_id + title + evidence` (sugerido en la spec) en vez de incluir también
    `description`/`severity`: un reintento del mismo tool-call por parte del agente (p. ej.
    tras un timeout) puede llegar con la descripción reformateada por el LLM (espacios,
    puntuación) sin que eso implique un hallazgo distinto, mientras que `title` + el
    conjunto exacto de citas de evidencia ya identifican unívocamente "el mismo hallazgo"
    para efectos de deduplicación en este slice. `evidence` se normaliza (orden
    determinista) antes de hashear para que el mismo conjunto de citas en distinto orden
    dé la misma clave.
    """
    normalized_evidence = sorted(
        ({"source": c["source"], "page": c.get("page")} for c in evidence),
        key=lambda c: (c["source"], c["page"] if c["page"] is not None else -1),
    )
    canonical = json.dumps(
        {"case_id": case_id, "title": title, "evidence": normalized_evidence},
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_existing_by_content_key(db: Session, case_id: str, key: str) -> Finding | None:
    """Busca, entre los hallazgos ya persistidos del mismo caso, uno con la misma clave.

    No requiere ninguna columna nueva en `Finding`: recalcula la misma clave determinista
    sobre `title`/`evidence` ya guardados y compara contra la clave del request actual.
    """
    candidates = db.query(Finding).filter(Finding.case_id == case_id).all()
    for candidate in candidates:
        candidate_key = _content_idempotency_key(
            candidate.case_id, candidate.title, candidate.evidence
        )
        if candidate_key == key:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Salida estructurada
# ---------------------------------------------------------------------------


def _finding_to_result(finding: Finding, *, idempotent_hit: bool) -> dict[str, Any]:
    """Serializa un `Finding` ORM al shape de salida tipado de la tool (regla 5)."""
    return {
        "finding_id": finding.id,
        "case_id": finding.case_id,
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity,
        "evidence": list(finding.evidence),
        "risk_score": finding.risk_score,
        "status": finding.status,
        "created_at": finding.created_at.isoformat(),
        "idempotent_hit": idempotent_hit,
    }


def _error(message: str, code: str) -> dict[str, str]:
    """Shape uniforme de error de tool (agentic-tool-use regla 2 / spec-003)."""
    return {"error": message, "code": code}


def _initial_status_for_severity(severity: str) -> str:
    """Deriva el status inicial de un hallazgo nuevo a partir de su severidad (spec-006).

    Espejo intencional de `app/routers/findings.py::_initial_status_for_severity` (mismo
    one-liner, misma constante `HIGH_RISK_SEVERITIES`): se duplica acá en vez de importar
    un símbolo privado de `backend-api` para no acoplar los dos módulos de dominio a los
    detalles internos del otro. Si esta regla cambia, debe actualizarse en ambos lugares.
    """
    return "pending_review" if severity in HIGH_RISK_SEVERITIES else "draft"


# ---------------------------------------------------------------------------
# La tool
# ---------------------------------------------------------------------------


def create_finding(tool_input: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
    """Tool invocable por el LLM: crea un hallazgo de auditoría.

    Args:
        tool_input: dict crudo recibido del LLM (ya viene deserializado de JSON por el
            framework de tool-calling, pero NO validado). Se valida acá contra
            `CreateFindingInput` antes de tocar cualquier lógica de negocio (regla 1).
        db: sesión de SQLAlchemy opcional (para tests / reuso de una sesión existente). Si
            no se pasa, la tool abre y cierra su propia sesión vía `SessionLocal()` (no hay
            `Depends()` disponible acá porque esto no corre dentro de un endpoint FastAPI).

    Returns:
        En éxito: dict con `finding_id`, `case_id`, `title`, `description`, `severity`,
        `evidence`, `risk_score`, `status`, `created_at`, `idempotent_hit` (bool: True si
        se detectó un reintento y se devolvió el hallazgo ya existente en vez de duplicar).

        En error: `{"error": str, "code": str}` — nunca una excepción cruda (regla 2).
        Códigos posibles: `invalid_input`, `audit_case_not_found`, `internal_error`.
    """
    try:
        try:
            parsed = CreateFindingInput.model_validate(tool_input)
        except ValidationError as exc:
            return _error(f"Input inválido para create_finding: {exc}", "invalid_input")

        owns_session = db is None
        session = db or SessionLocal()
        try:
            # 1) Idempotencia explícita (best-effort, en memoria de proceso).
            if parsed.idempotency_key is not None:
                cached_id = _EXPLICIT_IDEMPOTENCY_CACHE.get(parsed.idempotency_key)
                if cached_id is not None:
                    cached = session.get(Finding, cached_id)
                    if cached is not None:
                        return _finding_to_result(cached, idempotent_hit=True)

            case = session.get(AuditCase, parsed.case_id)
            if case is None:
                return _error(
                    f"Audit case no encontrado: {parsed.case_id}", "audit_case_not_found"
                )

            evidence_payload = [citation.model_dump() for citation in parsed.evidence]

            # 2) Idempotencia por contenido (persistida, sobrevive reinicios).
            content_key = _content_idempotency_key(parsed.case_id, parsed.title, evidence_payload)
            existing = _find_existing_by_content_key(session, parsed.case_id, content_key)
            if existing is not None:
                if parsed.idempotency_key is not None:
                    _EXPLICIT_IDEMPOTENCY_CACHE[parsed.idempotency_key] = existing.id
                return _finding_to_result(existing, idempotent_hit=True)

            risk_score = calculate_risk_score(parsed.severity, len(evidence_payload))

            finding = Finding(
                case_id=parsed.case_id,
                title=parsed.title,
                description=parsed.description,
                severity=parsed.severity,
                evidence=evidence_payload,
                risk_score=risk_score,
                status=_initial_status_for_severity(parsed.severity),
                # `triggered_by` nunca se acepta como parte de `tool_input`/`CreateFindingInput`
                # (el LLM no puede declarar su propia identidad): se fija acá en código, mismo
                # criterio que `app/routers/findings.py` aplica del lado humano con "human".
                triggered_by="llm",
            )
            session.add(finding)
            session.commit()
            session.refresh(finding)

            if parsed.idempotency_key is not None:
                _EXPLICIT_IDEMPOTENCY_CACHE[parsed.idempotency_key] = finding.id

            return _finding_to_result(finding, idempotent_hit=False)
        finally:
            if owns_session:
                session.close()
    except Exception as exc:  # noqa: BLE001 - red de seguridad final (spec-003 regla 2)
        return _error(f"Error inesperado creando hallazgo: {exc}", "internal_error")
