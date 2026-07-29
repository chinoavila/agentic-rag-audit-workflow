"""Pydantic schemas for a tool added to a project (spec-020).

`confirm` fue removido (spec-015, Bloque 3): un payload con `confirm` responde 422 vía
`extra="forbid"`, no se ignora silenciosamente. El mecanismo real de confirmación humana
antes de ejecutar un comando es `Chat.permission_mode` + `ToolRun`, ver
`app/schemas/chat.py`/`app/schemas/tool_run.py`.

Actualización (spec-013, Task 16): con el modelo default-on, `ProjectToolOut` deja de ser el
único shape de salida del router -- ahora representa exclusivamente la fila `ProjectTool`
(el override puntual), devuelta tal cual por `POST`/`PATCH .../tools`. `CaseToolOut` es el
shape nuevo de `GET .../tools`: la vista fusionada de catálogo instalado + override opcional,
con el estado `eligible` resuelto por el predicado único de
`app.services.tool_eligibility` (nunca recalculado en el schema ni en el router).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectToolCreate(BaseModel):
    tool_key: str = Field(..., min_length=1)


class ProjectToolPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    allowed_action_ids: list[str] | None = None


class ProjectToolOut(BaseModel):
    """Fila `ProjectTool` (override de proyecto), tal cual persistida.

    Devuelta por `POST`/`PATCH /api/audit-cases/{case_id}/tools...`. NO representa por sí
    sola la elegibilidad efectiva de una tool para un caso -- eso es responsabilidad de
    `CaseToolOut.eligible` (`GET .../tools`), que aplica el predicado de
    `app.services.tool_eligibility` sobre esta fila (si existe) más el catálogo global.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    tool_key: str
    enabled: bool
    allowed_action_ids: list[str]
    created_at: datetime


class CaseToolOut(BaseModel):
    """Vista fusionada de una tool para un caso (spec-013, Task 16).

    Una entrada por cada `ToolCatalogEntry.installed=true` del catálogo global, con su
    override de `ProjectTool` aplicado si existe (`project_tool=None` en el caso default-on:
    sin fila de override, la tool sigue siendo elegible). `eligible` es el resultado del
    predicado único de `app.services.tool_eligibility.list_eligible_tools` -- este schema
    nunca recalcula la regla, solo serializa lo que el router ya resolvió con el helper
    compartido.
    """

    model_config = ConfigDict(from_attributes=True)

    tool_key: str
    label: str
    description: str
    eligible: bool
    project_tool: ProjectToolOut | None = None
