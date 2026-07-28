"""Endpoints for `ToolRun` (spec-015).

`ToolRun` es append-only (mismo espíritu que `Finding`/`Report`, spec-004): no existe ni se
debe agregar ningún `db.delete(...)` sobre esta tabla en este router. El único mecanismo de
"corrección" tras un estado terminal es un `ToolRun` nuevo (nueva propuesta) -- no hay
`superseded_by` acá porque, a diferencia de `Finding`/`Report`, no hay contenido editable a
reemplazar, solo un ciclo de vida de aprobación.

Task 10 (spec-015) conecta este router con el sandbox REAL (`app/agentic_core/tool_execution/`,
Task 9) a través de `app/services/tool_run_execution.py` -- ese módulo es la única
implementación del ciclo `proposed -> approved -> executed/failed`; este router nunca invoca
`sandbox.execute` directamente ni reimplementa esa orquestación.

- `POST /api/chats/{chat_id}/tool-runs`: crea la propuesta (`status=proposed`), resolviendo
  `command_resuelto` (solo para mostrar/auditar) vía la allowlist -- NUNCA ejecuta acá. Es la
  interfaz que `agentic_core` (Task 12) invoca cuando el LLM propone una acción con `command`
  real.
- `PATCH /api/tool-runs/{id}`: transición humana `proposed -> approved|rejected`. Si el
  resultado es `approved`, este endpoint invoca el sandbox real de inmediato y persiste
  `executed`/`failed` -- nunca deja el `ToolRun` colgado en `status=approved` sin ejecutar. Un
  `rejected` nunca invoca el sandbox.
- `GET /api/chats/{chat_id}/tool-runs`: lectura de propuestas por chat.

El camino directo de `permission_mode=auto` con origen humano verificado (`proposed ->
executed/failed` sin pasar por `approved`) NO es un endpoint HTTP -- es
`app/services/tool_run_execution.py::create_and_execute_tool_run`, invocable directo en-proceso
por `agentic_core` (Task 12), documentado en el docstring de ese módulo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.chat import Chat
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.models.tool_run import ToolRun
from app.schemas.tool_run import (
    VALID_TOOL_RUN_PATCH_TRANSITIONS,
    ToolRunCreate,
    ToolRunOut,
    ToolRunPatch,
    ToolRunStatus,
)
from app.services.tool_run_execution import execute_tool_run, propose_tool_run

router = APIRouter(tags=["tool-runs"])


def _get_tool_run_or_404(db: Session, tool_run_id: str) -> ToolRun:
    tool_run = db.get(ToolRun, tool_run_id)
    if tool_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(
                status.HTTP_404_NOT_FOUND, "Tool run not found", "tool_run_not_found"
            ),
        )
    return tool_run


def _get_chat_or_404(db: Session, chat_id: str) -> Chat:
    chat = db.get(Chat, chat_id)
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(status.HTTP_404_NOT_FOUND, "Chat not found", "chat_not_found"),
        )
    return chat


@router.post(
    "/api/chats/{chat_id}/tool-runs",
    response_model=ToolRunOut,
    status_code=status.HTTP_201_CREATED,
)
def propose_tool_run_endpoint(
    chat_id: str,
    payload: ToolRunCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ToolRun:
    """Crea la propuesta de ejecución (`status=proposed`). Interfaz HTTP que `agentic_core`
    (Task 12) invoca cuando el LLM propone ejecutar una acción con `command` real dentro de un
    turno -- nunca ejecuta nada acá (ver `app/services/tool_run_execution.py::propose_tool_run`).

    `permission_mode_snapshot` se congela desde `Chat.permission_mode` vigente en este momento.
    `triggered_by="llm"` fijo server-side: este endpoint modela exclusivamente una propuesta
    generada por el loop del agente (nunca aceptado del body, `ToolRunCreate` ni siquiera
    declara ese campo).
    """
    chat = _get_chat_or_404(db, chat_id)
    tool = db.get(ToolCatalogEntry, payload.tool_key)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error_detail(status.HTTP_404_NOT_FOUND, "Tool not found", "tool_not_found"),
        )
    return propose_tool_run(
        db, chat, payload.tool_key, payload.action_id, payload.params, triggered_by="llm"
    )


@router.patch("/api/tool-runs/{tool_run_id}", response_model=ToolRunOut)
def patch_tool_run(
    tool_run_id: str,
    payload: ToolRunPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ToolRun:
    """Transiciona un `ToolRun` de `status=proposed` a `approved`/`rejected`, seteando
    `resolved_by`/`triggered_by="human"` del caller. Solo callable por un usuario humano
    autenticado -- nunca invocado por el LLM (ver `app/deps.py::get_current_user`).

    Rechaza cualquier transición cuyo origen no sea `status=proposed` con un 400 del
    contrato de error uniforme (spec-010, set de status codes restringido -- 409 no es un
    código documentado): un `ToolRun` ya resuelto (`approved`/`rejected`/`executed`/`failed`)
    es un estado terminal para este endpoint.

    Task 10: si `payload.status == "approved"`, este endpoint invoca de inmediato el sandbox
    REAL (`app/services/tool_run_execution.py::execute_tool_run`) y persiste el resultado --
    nunca deja el `ToolRun` colgado en `status=approved` sin ejecutar. `command_resuelto`
    editado (si vino en el payload) queda persistido para auditoría/visualización, pero la
    ejecución real siempre re-resuelve el `argv` desde `(tool_key, action_id, params_json)` vía
    la allowlist -- nunca desde este texto editado (spec-015, punto 1: nunca texto libre no
    validado). Un `rejected` nunca invoca el sandbox.
    """
    tool_run = _get_tool_run_or_404(db, tool_run_id)

    valid_targets = VALID_TOOL_RUN_PATCH_TRANSITIONS.get(tool_run.status, set())
    if payload.status not in valid_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error_detail(
                status.HTTP_400_BAD_REQUEST,
                (
                    f"Invalid transition: tool_run.status='{tool_run.status}' cannot move to "
                    f"'{payload.status}' via PATCH"
                ),
                "invalid_tool_run_transition",
            ),
        )

    tool_run.status = payload.status
    # Server-side siempre: este endpoint HTTP solo representa una aprobación/rechazo humano
    # (nunca el LLM, que no tiene ninguna tool ni mecanismo para invocarlo).
    tool_run.triggered_by = "human"
    tool_run.resolved_by = current_user.id
    if payload.command_resuelto is not None:
        tool_run.command_resuelto = payload.command_resuelto

    db.commit()
    db.refresh(tool_run)

    if payload.status == "approved":
        tool_run = execute_tool_run(db, tool_run)

    return tool_run


@router.get("/api/chats/{chat_id}/tool-runs", response_model=list[ToolRunOut])
def list_tool_runs_by_chat(
    chat_id: str,
    status: ToolRunStatus | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ToolRun]:
    """Lista `ToolRun` de un chat, más recientes primero, con filtro opcional `?status=`.

    Permite a la UI descubrir propuestas pendientes de aprobación (`status=proposed`) para
    un chat determinado. El parámetro se llama `status` (no `status_filter`) para respetar el
    contrato de query string de la spec (`GET /api/chats/{chat_id}/tool-runs?status=`); no
    colisiona con `fastapi.status` (códigos HTTP) porque esta función no lo referencia.
    """
    _get_chat_or_404(db, chat_id)
    query = db.query(ToolRun).filter(ToolRun.chat_id == chat_id)
    if status is not None:
        query = query.filter(ToolRun.status == status)
    return query.order_by(ToolRun.created_at.desc()).all()
