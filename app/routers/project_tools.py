"""Endpoints for tools added to a specific project (spec-020).

No append-only (ver `app/models/project_tool.py`): a diferencia de `Finding`/`Report`, esto es
configuración de UI, así que `DELETE` acá es un `db.delete(...)` real -- no viola
`restricted-ops.json` (esa regla es específica de las tablas de audit trail: findings, reports,
audit_trail; `project_tools` no es una de ellas).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.audit_case import AuditCase
from app.models.project_tool import ProjectTool
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.schemas.project_tool import ProjectToolCreate, ProjectToolOut, ProjectToolPatch

router = APIRouter(prefix="/api/audit-cases", tags=["project-tools"])


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


def _get_project_tool_or_404(db: Session, case_id: str, tool_key: str) -> ProjectTool:
    pt = (
        db.query(ProjectTool)
        .filter(ProjectTool.case_id == case_id, ProjectTool.tool_key == tool_key)
        .first()
    )
    if pt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Tool not added to this project", "project_tool_not_found"
            ),
        )
    return pt


@router.get("/{case_id}/tools", response_model=list[ProjectToolOut])
def list_project_tools(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ProjectTool]:
    _get_case_or_404(db, case_id)
    return db.query(ProjectTool).filter(ProjectTool.case_id == case_id).all()


@router.post("/{case_id}/tools", response_model=ProjectToolOut, status_code=status.HTTP_201_CREATED)
def add_project_tool(
    case_id: str,
    payload: ProjectToolCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProjectTool:
    _get_case_or_404(db, case_id)
    tool = db.get(ToolCatalogEntry, payload.tool_key)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(status.HTTP_404_NOT_FOUND, "Tool not found", "tool_not_found"),
        )
    existing = (
        db.query(ProjectTool)
        .filter(ProjectTool.case_id == case_id, ProjectTool.tool_key == payload.tool_key)
        .first()
    )
    if existing is not None:
        return existing

    project_tool = ProjectTool(
        case_id=case_id,
        tool_key=payload.tool_key,
        allowed_action_ids=[a["id"] for a in tool.actions],
    )
    db.add(project_tool)
    db.commit()
    db.refresh(project_tool)
    return project_tool


@router.patch("/{case_id}/tools/{tool_key}", response_model=ProjectToolOut)
def patch_project_tool(
    case_id: str,
    tool_key: str,
    payload: ProjectToolPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProjectTool:
    project_tool = _get_project_tool_or_404(db, case_id, tool_key)
    if payload.enabled is not None:
        project_tool.enabled = payload.enabled
    if payload.allowed_action_ids is not None:
        project_tool.allowed_action_ids = payload.allowed_action_ids
    db.commit()
    db.refresh(project_tool)
    return project_tool


@router.delete("/{case_id}/tools/{tool_key}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_tool(
    case_id: str,
    tool_key: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    project_tool = _get_project_tool_or_404(db, case_id, tool_key)
    db.delete(project_tool)
    db.commit()
