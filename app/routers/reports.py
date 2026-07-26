"""Endpoints for generated audit reports (spec-011, spec-012).

Mismo patrón que `app/routers/findings.py`:

1. Sin `POST`: la creación es responsabilidad exclusiva de la tool `generate_report`
   (`app/tools/generate_report.py`), que corre las rúbricas de spec-012 antes de persistir --
   un `POST` HTTP directo podría saltearlas, así que no se expone.
2. Sin `DELETE` físico (spec-011): `PATCH` es la única forma de mutar un `Report` tras su
   creación (transición de status y/o `superseded_by`).
3. Todo `Report` requiere aprobación humana antes de `published` (spec-006 aplicado a
   reportes) -- a diferencia de `Finding`, acá no hay excepción por severidad: ningún
   informe se publica sin el gate.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.report import Report
from app.reports.storage import read_report_blob
from app.schemas.report import ReportOut, ReportPatch

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_report_or_404(db: Session, report_id: str) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Report not found", "report_not_found"
            ),
        )
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(
    skip: int = 0,
    limit: int = 100,
    case_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Report]:
    """Lista reportes, paginado y filtrable por `case_id` (incluye superseded, spec-011)."""
    query = db.query(Report)
    if case_id is not None:
        query = query.filter(Report.case_id == case_id)
    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Report:
    """Obtiene un reporte por id (incluye reportes superseded, para preservar historial)."""
    return _get_report_or_404(db, report_id)


@router.get("/{report_id}/content")
def get_report_content(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Devuelve el texto renderizado del informe desde el blob storage (spec-011): un
    reporte supersedido sigue siendo accesible tal cual vía su `report_id` histórico.
    """
    report = _get_report_or_404(db, report_id)
    return {"report_id": report.id, "content": read_report_blob(report.blob_path)}


@router.patch("/{report_id}", response_model=ReportOut)
def patch_report(
    report_id: str,
    payload: ReportPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Report:
    """Única forma de mutar un reporte tras su creación: supersede y/o transición de status.

    Nunca implementa ni permite un `db.delete(...)` sobre `Report` (spec-011). El body no
    admite `title`/`sections`/`blob_path`: el contenido de un informe ya generado es
    inmutable.
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

    report = _get_report_or_404(db, report_id)

    if payload.superseded_by is not None:
        if payload.superseded_by == report.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_error_detail(
                    status.HTTP_400_BAD_REQUEST,
                    "A report cannot supersede itself",
                    "invalid_supersede_target",
                ),
            )
        replacement = db.get(Report, payload.superseded_by)
        if replacement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error_detail(
                    status.HTTP_404_NOT_FOUND,
                    "superseded_by target report not found",
                    "report_not_found",
                ),
            )
        report.superseded_by = payload.superseded_by

    if payload.status is not None:
        new_status = payload.status
        # Todo reporte requiere aprobación humana antes de "published" (spec-006 aplicado a
        # reportes) -- a diferencia de findings, acá no hay excepción por severidad.
        requires_approval = new_status == "published"
        approved_by = payload.approved_by or report.approved_by

        if requires_approval and not approved_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_error_detail(
                    status.HTTP_400_BAD_REQUEST,
                    (
                        "Publishing a report requires approved_by before transitioning to "
                        "status=published (spec-006 human-in-the-loop)"
                    ),
                    "approval_required",
                ),
            )

        if payload.approved_by is not None:
            report.approved_by = payload.approved_by
            report.approved_at = datetime.now(timezone.utc)

        report.status = new_status

    db.commit()
    db.refresh(report)
    return report
