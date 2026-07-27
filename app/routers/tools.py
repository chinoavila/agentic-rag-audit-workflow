"""Endpoints for the global tool catalog (spec-020).

Sin `POST /{key}/invoke` a propósito, todavía: ejecutar una tool desde este catálogo (más
allá del loop de tool-calling del LLM, que ya usa `TOOL_DISPATCH` directo, ver
`app/agentic_core/tools_registry.py`) requiere decidir primero cómo autorizar/loguear esa
invocación humana explícita (`ToolRun`, ya diseñado en el plan de migración pero no
implementado en este slice) y, para una entry sin ejecutor real registrado (creada a mano
desde `POST /api/tools`), no hay ninguna función Python que la corra -- el campo
`actions[].command` es metadata descriptiva, nunca un comando que este backend ejecute. Ver
`app/models/tool_catalog_entry.py` para el detalle completo de esta decisión.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.schemas.tool_catalog import ToolCatalogEntryCreate, ToolCatalogEntryOut, ToolCatalogEntryPatch

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug or "herramienta"


def _get_tool_or_404(db: Session, key: str) -> ToolCatalogEntry:
    tool = db.get(ToolCatalogEntry, key)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(status.HTTP_404_NOT_FOUND, "Tool not found", "tool_not_found"),
        )
    return tool


@router.get("", response_model=list[ToolCatalogEntryOut])
def list_tools(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ToolCatalogEntry]:
    return db.query(ToolCatalogEntry).order_by(ToolCatalogEntry.created_at.asc()).all()


@router.post("", response_model=ToolCatalogEntryOut, status_code=status.HTTP_201_CREATED)
def create_tool(
    payload: ToolCatalogEntryCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ToolCatalogEntry:
    """Alta de una entry de catálogo metadata-only (ver docstring del módulo)."""
    key = payload.key or _slugify(payload.label)
    if db.get(ToolCatalogEntry, key) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error_detail(
                status.HTTP_400_BAD_REQUEST, f"Ya existe una tool con key '{key}'", "tool_key_conflict"
            ),
        )
    tool = ToolCatalogEntry(
        key=key,
        label=payload.label,
        description=payload.description,
        kind=payload.kind,
        installed=True,
        actions=[a.model_dump() for a in payload.actions],
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


@router.patch("/{key}", response_model=ToolCatalogEntryOut)
def patch_tool(
    key: str,
    payload: ToolCatalogEntryPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ToolCatalogEntry:
    tool = _get_tool_or_404(db, key)
    if payload.label is not None:
        tool.label = payload.label
    if payload.description is not None:
        tool.description = payload.description
    if payload.kind is not None:
        tool.kind = payload.kind
    if payload.installed is not None:
        tool.installed = payload.installed
    if payload.actions is not None:
        tool.actions = [a.model_dump() for a in payload.actions]
    db.commit()
    db.refresh(tool)
    return tool
