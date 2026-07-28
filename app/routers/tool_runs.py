"""Endpoints for `ToolRun` (spec-015).

`ToolRun` es append-only (mismo espíritu que `Finding`/`Report`, spec-004): no existe ni se
debe agregar ningún `db.delete(...)` sobre esta tabla en este router. El único mecanismo de
"corrección" tras un estado terminal es un `ToolRun` nuevo (nueva propuesta) -- no hay
`superseded_by` acá porque, a diferencia de `Finding`/`Report`, no hay contenido editable a
reemplazar, solo un ciclo de vida de aprobación.

Este router modela exclusivamente la transición humana `proposed -> approved|rejected` (vía
`PATCH`) y la lectura de propuestas por chat (`GET`). La creación de un `ToolRun` en
`status=proposed`, y las transiciones hacia `executed`/`failed` que produce la ejecución real
en el sandbox, son responsabilidad del loop agéntico y del sandbox de security-compliance
(Task 9/10 del plan de migración) -- fuera de alcance de este módulo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.errors import api_error_detail
from app.models.chat import Chat
from app.models.tool_run import ToolRun
from app.schemas.tool_run import VALID_TOOL_RUN_PATCH_TRANSITIONS, ToolRunOut, ToolRunPatch, ToolRunStatus

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
