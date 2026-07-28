"""Endpoints for audit case management.

Ver `.ai/skills/fastapi/SKILL.md` (prefijo `/api/...`, paginación, schemas Pydantic, auth
vía `Depends`, contrato de error uniforme) y spec-007 (aislamiento de sesión/auth).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.audit_case import AuditCase
from app.schemas.audit_case import AuditCaseCreate, AuditCaseOut, AuditCasePatch

router = APIRouter(prefix="/api/audit-cases", tags=["audit-cases"])


def _get_case_or_404(db: Session, case_id: str) -> AuditCase:
    case = db.get(AuditCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Audit case not found", "audit_case_not_found"
            ),
        )
    return case


@router.post("", response_model=AuditCaseOut, status_code=status.HTTP_201_CREATED)
def create_audit_case(
    payload: AuditCaseCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AuditCase:
    """Crea un nuevo caso de auditoría (proyecto)."""
    case = AuditCase(name=payload.name, status=payload.status, context=payload.context)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[AuditCaseOut])
def list_audit_cases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AuditCase]:
    """Lista casos de auditoría no archivados, paginado (`skip`/`limit`, ver fastapi SKILL regla 2)."""
    return (
        db.query(AuditCase)
        .filter(AuditCase.status != "archived")
        .order_by(AuditCase.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{case_id}", response_model=AuditCaseOut)
def get_audit_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AuditCase:
    """Obtiene un caso de auditoría por id."""
    return _get_case_or_404(db, case_id)


@router.patch("/{case_id}", response_model=AuditCaseOut)
def patch_audit_case(
    case_id: str,
    payload: AuditCasePatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AuditCase:
    """Edita nombre, contexto y/o status de un proyecto ya creado (spec-020)."""
    case = _get_case_or_404(db, case_id)
    if payload.name is not None:
        case.name = payload.name
    if payload.context is not None:
        case.context = payload.context
    if payload.status is not None:
        case.status = payload.status
    db.commit()
    db.refresh(case)
    return case
