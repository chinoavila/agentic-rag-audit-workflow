"""Predicado único de elegibilidad de tools (spec-013, Task 18).

Única implementación en el codebase de la regla:

    elegible == ToolCatalogEntry.installed == True
                AND (no existe fila ProjectTool para (case_id, tool_key)
                     OR ProjectTool.enabled == True)

Consumida, sin reimplementar, por:
- El pipeline de indexación de tool-docs de retrieval (`rag-engineer`, spec-013 Task 11):
  filtra el subconjunto elegible ANTES de aplicar `SIMILARITY_THRESHOLD` (spec-008).
- `GET /api/audit-cases/{case_id}/tools` (`backend-api`, spec-013 Task 16): vista fusionada
  de catálogo instalado menos overrides de proyecto.

Caso `case_id=None` (chat standalone, sin proyecto): `ProjectTool.case_id` es una FK NOT NULL
a `AuditCase` (ver `app/models/project_tool.py`), así que nunca puede existir una fila
`ProjectTool` asociada a `case_id=None`. En ese caso el predicado colapsa a
`ToolCatalogEntry.installed == True` -- no hay override posible que evaluar.

El catálogo global (`installed`) siempre tiene precedencia absoluta sobre cualquier override
de proyecto: una tool con `installed=False` nunca es elegible, exista o no una fila
`ProjectTool.enabled=True` para algún `case_id`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.project_tool import ProjectTool
from app.models.tool_catalog_entry import ToolCatalogEntry


def _eligible(installed: bool, project_tool: ProjectTool | None) -> bool:
    """Predicado puro, sin acceso a DB -- el único lugar donde vive la regla de negocio.

    `is_tool_eligible` y `list_eligible_tools` son ambos wrappers de esta función que solo
    difieren en cómo obtienen `installed`/`project_tool`; ninguno reimplementa la regla.
    """
    if not installed:
        return False
    if project_tool is None:
        return True
    return project_tool.enabled


def is_tool_eligible(db: Session, case_id: str | None, tool_key: str) -> bool:
    """True si `tool_key` es elegible para `case_id` (o para el chat standalone si es None).

    Una `tool_key` que no existe en el catálogo global nunca es elegible (equivalente a
    `installed=False`).
    """
    entry = db.get(ToolCatalogEntry, tool_key)
    if entry is None:
        return False

    project_tool: ProjectTool | None = None
    if case_id is not None:
        project_tool = (
            db.query(ProjectTool)
            .filter(ProjectTool.case_id == case_id, ProjectTool.tool_key == tool_key)
            .first()
        )

    return _eligible(entry.installed, project_tool)


def list_eligible_tools(db: Session, case_id: str | None) -> list[ToolCatalogEntry]:
    """Subconjunto elegible del catálogo global para `case_id` (o para el chat standalone).

    Devuelve instancias `ToolCatalogEntry` (nunca `ProjectTool`): el override de proyecto solo
    decide inclusión/exclusión, no reemplaza los datos de catálogo que el caller necesita
    (label/description/actions) para indexar o serializar la tool.
    """
    entries = db.query(ToolCatalogEntry).order_by(ToolCatalogEntry.created_at.asc()).all()

    project_tools_by_key: dict[str, ProjectTool] = {}
    if case_id is not None:
        rows = db.query(ProjectTool).filter(ProjectTool.case_id == case_id).all()
        project_tools_by_key = {row.tool_key: row for row in rows}

    return [
        entry
        for entry in entries
        if _eligible(entry.installed, project_tools_by_key.get(entry.key))
    ]
