"""Endpoints for tool elegibility/overrides on a specific project (spec-020, spec-013 Task 16).

No append-only (ver `app/models/project_tool.py`): a diferencia de `Finding`/`Report`, esto es
configuración de UI, así que `DELETE` acá es un `db.delete(...)` real -- no viola
`restricted-ops.json` (esa regla es específica de las tablas de audit trail: findings, reports,
audit_trail; `project_tools` no es una de ellas).

Actualización (spec-013, Task 16): el modelo de elegibilidad pasó de opt-in a default-on (ver
`app/services/tool_eligibility.py`, predicado único, Task 18): `ToolCatalogEntry.installed=true`
alcanza para que una tool esté disponible en todo proyecto; `ProjectTool` deja de significar
"la tool está agregada a este proyecto" y pasa a significar exclusivamente "override puntual de
inclusión/exclusión para este `case_id`". Este router consume `tool_eligibility` para resolver
el estado efectivo de cada tool -- nunca reimplementa el predicado (`installed AND (sin fila
ProjectTool OR ProjectTool.enabled)`).
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
from app.schemas.project_tool import CaseToolOut, ProjectToolCreate, ProjectToolOut, ProjectToolPatch
from app.services.tool_eligibility import list_eligible_tools

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


@router.get("/{case_id}/tools", response_model=list[CaseToolOut])
def list_project_tools(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CaseToolOut]:
    """Vista fusionada default-on (spec-013): una entrada por cada `ToolCatalogEntry.installed
    =true` del catálogo global, con su override de `ProjectTool` aplicado si existe.

    La ausencia de fila `ProjectTool` para `(case_id, tool_key)` ya NO significa "no
    disponible" -- significa "elegible por default, sin override". `eligible` refleja el
    predicado único de `app.services.tool_eligibility.list_eligible_tools`, consumido acá tal
    cual (nunca recalculado en este router).
    """
    _get_case_or_404(db, case_id)

    installed_entries = (
        db.query(ToolCatalogEntry)
        .filter(ToolCatalogEntry.installed.is_(True))
        .order_by(ToolCatalogEntry.created_at.asc())
        .all()
    )
    eligible_keys = {entry.key for entry in list_eligible_tools(db, case_id)}
    project_tools_by_key = {
        pt.tool_key: pt
        for pt in db.query(ProjectTool).filter(ProjectTool.case_id == case_id).all()
    }

    return [
        CaseToolOut(
            tool_key=entry.key,
            label=entry.label,
            description=entry.description,
            eligible=entry.key in eligible_keys,
            project_tool=(
                ProjectToolOut.model_validate(project_tools_by_key[entry.key])
                if entry.key in project_tools_by_key
                else None
            ),
        )
        for entry in installed_entries
    ]


@router.post("/{case_id}/tools", response_model=ProjectToolOut, status_code=status.HTTP_201_CREATED)
def add_project_tool(
    case_id: str,
    payload: ProjectToolCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProjectTool:
    """Crea el override de `ProjectTool` para `(case_id, payload.tool_key)`.

    Cambio de semántica (spec-013, Task 16): con el modelo default-on, una tool con
    `ToolCatalogEntry.installed=true` ya está disponible en el proyecto sin necesidad de esta
    llamada -- este endpoint deja de significar "agregar la tool al proyecto" y pasa a
    significar "crear el override puntual de inclusión/exclusión" para ese `case_id` (la fila
    `ProjectTool`; edición posterior de `enabled`/`allowed_action_ids` vía `PATCH`). Se
    mantiene el verbo/ruta (`POST .../tools`) para no romper el contrato HTTP existente -- ver
    spec-013 y `docs/plans/plan-tool-execution-permission-modes.md` sección 3.

    Rechaza con 400 si `payload.tool_key` no está instalada globalmente
    (`ToolCatalogEntry.installed=false`): el catálogo global tiene precedencia absoluta
    (spec-013) y una tool desinstalada nunca es elegible, exista o no un override de
    proyecto -- no tiene sentido crear uno.
    """
    _get_case_or_404(db, case_id)
    tool = db.get(ToolCatalogEntry, payload.tool_key)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(status.HTTP_404_NOT_FOUND, "Tool not found", "tool_not_found"),
        )
    if not tool.installed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error_detail(
                status.HTTP_400_BAD_REQUEST,
                f"Tool '{tool.key}' is not installed in the global catalog",
                "tool_not_installed",
            ),
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
