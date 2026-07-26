"""Endpoints for audit findings.

Reglas de negocio críticas aplicadas acá (ver `.ai/skills/audit-domain-rules/SKILL.md` y
`.ai/specs/audit/spec-004-inmutabilidad-audit-trail.md` /
`.ai/specs/audit/spec-006-human-in-the-loop.md`):

1. Un hallazgo `high`/`critical` nunca se crea directo en `final`: al crearse, si su
   severidad es `high`/`critical` entra en `pending_review`; si es `low`/`medium` entra en
   `draft`. El cliente (audit-tools/agentic-core) no puede pasar `status` en la creación.
2. La transición a `status=final` de un hallazgo `high`/`critical` requiere `approved_by`
   (seteado en este request o ya presente de un request anterior); `approved_at` lo setea
   siempre el servidor, nunca el cliente, al momento de la aprobación.
3. Nunca se expone un DELETE físico. "Eliminar" es `PATCH` con `superseded_by=<new_id>`,
   que preserva el registro original (`id`, `created_at`, contenido) intacto.
4. `status=rejected` (spec-006, botón "reject" de chainlit-ui) es un estado terminal
   distinto de `final`: NO requiere `approved_by`/`approved_at` (esos campos documentan
   quién *aprobó* un hallazgo `final`, no quién lo rechazó). Si además querés registrar
   quién rechazó, reusá `approved_by` mandándolo explícitamente en el mismo PATCH — el
   campo no se renombra para evitar una migración; queda "sin poblar" si el caller no lo
   manda, lo cual es válido. El router no implementa una máquina de estados explícita para
   `status` (ninguna transición previa la tenía tampoco, ver punto 2): revertir un
   `rejected` es responsabilidad del caller vía un nuevo `PATCH status=...`, y "deshacer"
   un rechazo en el sentido de auditoría (spec-004, append-only) se hace creando un nuevo
   `Finding` y usando `superseded_by`, no reescribiendo el status del original.
5. `triggered_by` (spec-005) nunca viene del cliente (no existe en `FindingCreate`): este
   router fija `"human"` a mano en `create_finding` porque este endpoint HTTP directo
   siempre representa creación humana en este sistema.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.audit_case import AuditCase
from app.models.finding import Finding
from app.schemas.finding import HIGH_RISK_SEVERITIES, FindingCreate, FindingOut, FindingPatch

router = APIRouter(prefix="/api/findings", tags=["findings"])


def _initial_status_for_severity(severity: str) -> str:
    """Deriva el status inicial de un hallazgo nuevo a partir de su severidad (spec-006)."""
    return "pending_review" if severity in HIGH_RISK_SEVERITIES else "draft"


def _get_finding_or_404(db: Session, finding_id: str) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Finding not found", "finding_not_found"
            ),
        )
    return finding


@router.post("", response_model=FindingOut, status_code=status.HTTP_201_CREATED)
def create_finding(
    payload: FindingCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Finding:
    """Crea un hallazgo. `evidence` vacío es rechazado con 422 por `FindingCreate`."""
    case = db.get(AuditCase, payload.case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Audit case not found", "audit_case_not_found"
            ),
        )

    finding = Finding(
        case_id=payload.case_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        evidence=[citation.model_dump() for citation in payload.evidence],
        risk_score=payload.risk_score,
        status=_initial_status_for_severity(payload.severity),
        # Fijado server-side siempre: este endpoint HTTP directo es siempre creación
        # humana (spec-005, hallazgo B). La tool del LLM (create_finding) no pasa por
        # este router — escribe "llm" directo contra el ORM.
        triggered_by="human",
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("", response_model=list[FindingOut])
def list_findings(
    skip: int = 0,
    limit: int = 100,
    case_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Finding]:
    """Lista hallazgos, paginado y filtrable por `case_id`."""
    query = db.query(Finding)
    if case_id is not None:
        query = query.filter(Finding.case_id == case_id)
    return query.order_by(Finding.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{finding_id}", response_model=FindingOut)
def get_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Finding:
    """Obtiene un hallazgo por id (incluye hallazgos superseded, para preservar historial)."""
    return _get_finding_or_404(db, finding_id)


@router.patch("/{finding_id}", response_model=FindingOut)
def patch_finding(
    finding_id: str,
    payload: FindingPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Finding:
    """Única forma de mutar un hallazgo tras su creación: supersede y/o transición de status.

    Nunca implementa ni permite un `db.delete(...)` sobre `Finding` (spec-004). El body no
    admite `title`/`description`/`evidence`/`severity`: el contenido de un hallazgo ya
    creado es inmutable.
    """
    if payload.status is None and payload.superseded_by is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error_detail(
                status.HTTP_400_BAD_REQUEST,
                "Must provide at least one of: status, superseded_by",
                "empty_patch_payload",
            ),
        )

    finding = _get_finding_or_404(db, finding_id)

    if payload.superseded_by is not None:
        if payload.superseded_by == finding.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_error_detail(
                    status.HTTP_400_BAD_REQUEST,
                    "A finding cannot supersede itself",
                    "invalid_supersede_target",
                ),
            )
        replacement = db.get(Finding, payload.superseded_by)
        if replacement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error_detail(
                    status.HTTP_404_NOT_FOUND,
                    "superseded_by target finding not found",
                    "finding_not_found",
                ),
            )
        finding.superseded_by = payload.superseded_by

    if payload.status is not None:
        new_status = payload.status
        # Solo la transición a "final" en severidades altas exige approved_by (spec-006).
        # "rejected" es un estado terminal distinto: no pasa por esta puerta (ver docstring).
        requires_approval = new_status == "final" and finding.severity in HIGH_RISK_SEVERITIES
        approved_by = payload.approved_by or finding.approved_by

        if requires_approval and not approved_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_error_detail(
                    status.HTTP_400_BAD_REQUEST,
                    (
                        "High/critical findings require approved_by before transitioning "
                        "to status=final (spec-006 human-in-the-loop)"
                    ),
                    "approval_required",
                ),
            )

        if payload.approved_by is not None:
            finding.approved_by = payload.approved_by
            finding.approved_at = datetime.now(timezone.utc)

        finding.status = new_status

    db.commit()
    db.refresh(finding)
    return finding
