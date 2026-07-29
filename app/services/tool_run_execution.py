"""Orquestación entre `ToolRun` (persistencia, Task 8), la allowlist/sandbox reales
(`app/agentic_core/tool_execution/`, Task 9) y los endpoints HTTP (`app/routers/tool_runs.py`,
Task 10) -- spec-015.

Este módulo es la ÚNICA implementación del ciclo `proposed -> approved -> executed/failed` (y
del atajo `proposed -> executed/failed` directo para `permission_mode=auto` con origen humano
verificado) -- ni `app/routers/tool_runs.py` ni el futuro loop de `agentic_core` (Task 12)
deben reimplementar esta lógica ni llamar a `sandbox.execute` directamente por su cuenta.

## Contrato hacia Task 12 (agentic-core)

`create_and_execute_tool_run(db, chat_id, tool_key, action_id, params=None) -> ToolRun` es la
función que el loop del agente debe invocar directamente, in-process (mismo patrón que
`TOOL_DISPATCH` en `app/agentic_core/tools_registry.py` invoca `search_evidence`/
`create_finding`/`generate_report`: una llamada Python pura, nunca un round-trip HTTP interno),
para la rama `permission_mode=auto` **solo cuando el loop ya verificó** que el origen de la
propuesta es un turno humano explícito (spec-015, "criterio testeable de origen humano": ningún
mensaje `role=tool` anexado todavía en la invocación actual de `run_agent_turn`). Esta función
NO vuelve a verificar esa condición -- confía en que el caller (Task 12) solo la invoca desde
esa rama exacta del árbol de decisión de permission_mode. Transiciona
`proposed -> executed`/`failed` directo, NUNCA pasa por `approved` (ese estado es exclusivo del
flujo humano vía `PATCH /api/tool-runs/{id}`, ver `app/routers/tool_runs.py`).

Para `manual`/`accept_edit` (y para el caso degradado de `auto` sin origen verificado), Task 12
debe en cambio invocar el endpoint HTTP `POST /api/chats/{chat_id}/tool-runs` (o, si el loop
corre en el mismo proceso que el server HTTP, puede llamar `propose_tool_run` de este módulo
directamente con `triggered_by="llm"`) y cortar el turno sin ejecutar -- la aprobación humana
posterior llega vía `PATCH /api/tool-runs/{id}`, que ya está conectado a `execute_tool_run` acá
mismo.
"""

from __future__ import annotations

import json
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.agentic_core.tool_execution import sandbox
from app.agentic_core.tool_execution.allowlist import get_entry
from app.models.chat import Chat
from app.models.tool_run import ToolRun


def _serialize_params(params: dict[str, Any] | None) -> str:
    return json.dumps(params or {}, sort_keys=True)


def _deserialize_params(params_json: str | None) -> dict[str, Any]:
    if not params_json:
        return {}
    try:
        loaded = json.loads(params_json)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _preview_command_resuelto(tool_key: str, action_id: str, params: dict[str, Any] | None) -> str:
    """Representación SOLO para mostrar a humanos/auditoría (nunca se re-parsea para ejecutar,
    ver docstring de `app/models/tool_run.py`). Si la entrada de la allowlist resuelve el
    `argv` con los `params` propuestos, se muestra ese `argv` (vía `shlex.join`, seguro para
    mostrar/copiar aunque nunca se ejecuta desde acá). Si no hay entrada o los `params` no
    validan todavía, se deja un texto descriptivo explícito -- la propuesta igual se persiste
    (`status=proposed`); recién en la ejecución real (`execute_tool_run`) esto se traduce a
    `status=failed`, `error_code="no_allowlist_entry"` (spec-015, punto 1).
    """
    entry = get_entry(tool_key, action_id)
    if entry is not None:
        argv = entry.resolve_argv(params)
        if argv is not None:
            return shlex.join(argv)
    return (
        f"{tool_key} {action_id} params={_serialize_params(params)} "
        "(sin resolver: no hay entrada de allowlist o los parámetros no validan todavía)"
    )


def propose_tool_run(
    db: Session,
    chat: Chat,
    tool_key: str,
    action_id: str,
    params: dict[str, Any] | None = None,
    *,
    triggered_by: str = "llm",
) -> ToolRun:
    """Crea un `ToolRun` en `status=proposed`, congelando `permission_mode_snapshot` desde
    `chat.permission_mode` vigente -- NUNCA ejecuta (spec-015, "Endpoints de API para
    ToolRun", punto 1 de la task). Usado tanto por `POST /api/chats/{chat_id}/tool-runs` (Task
    12 vía HTTP) como por `create_and_execute_tool_run` (Task 12 vía invocación directa,
    camino `auto`).
    """
    tool_run = ToolRun(
        chat_id=chat.id,
        tool_key=tool_key,
        action_id=action_id,
        command_resuelto=_preview_command_resuelto(tool_key, action_id, params),
        params_json=_serialize_params(params),
        permission_mode_snapshot=chat.permission_mode,
        status="proposed",
        triggered_by=triggered_by,
    )
    db.add(tool_run)
    db.commit()
    db.refresh(tool_run)
    return tool_run


def execute_tool_run(db: Session, tool_run: ToolRun) -> ToolRun:
    """Invoca el sandbox REAL (`sandbox.execute`, Task 9) para un `ToolRun` ya aprobado (o
    recién propuesto en el camino directo de `auto`) y persiste el resultado -- nunca deja al
    `ToolRun` en `status=approved` sin ejecutar (spec-015, punto 2 de la task).

    `sandbox.execute` nunca deja escapar una excepción cruda (contrato documentado en su propio
    docstring); este wrapper tampoco necesita un `try/except` adicional para eso, pero sí
    normaliza el resultado al shape exacto de columnas de `ToolRun` (spec-015, Bloque 1):
    `error_code` restringido al set cerrado, `exit_code` solo poblado cuando corresponde.
    """
    params = _deserialize_params(tool_run.params_json)
    result = sandbox.execute(tool_run.tool_key, tool_run.action_id, params)

    if result.get("status") == "executed":
        tool_run.status = "executed"
        tool_run.exit_code = result.get("exit_code")
        tool_run.error_code = None
        tool_run.error_detail = None
    else:
        tool_run.status = "failed"
        tool_run.error_code = result.get("error_code")
        tool_run.error_detail = result.get("error_detail")
        # `exit_code` solo se puebla si el propio sandbox lo trae (p. ej. nonzero_exit) --
        # timeout/no_allowlist_entry no tienen exit_code real (spec-015, Bloque 1).
        tool_run.exit_code = result.get("exit_code")

    # Task 12 (agentic-core): persiste la salida real -- ya truncada/sanitizada por
    # `sandbox._truncate` -- para que el loop pueda devolverla al LLM (envuelta en
    # `<untrusted_context>`) y la UI pueda mostrarla en estados terminales. `None` si el
    # sandbox nunca llegó a correr un proceso real (p. ej. `no_allowlist_entry`).
    tool_run.stdout = result.get("stdout")
    tool_run.stderr = result.get("stderr")

    db.commit()
    db.refresh(tool_run)
    return tool_run


def create_and_execute_tool_run(
    db: Session,
    chat_id: str,
    tool_key: str,
    action_id: str,
    params: dict[str, Any] | None = None,
) -> ToolRun:
    """CONTRATO para `agentic_core` (Task 12) -- camino directo de `permission_mode=auto` con
    origen humano ya verificado por el caller (ver docstring del módulo). Crea el `ToolRun`
    (`triggered_by="llm"` fijo server-side -- la propuesta la generó el LLM, aunque la decisión
    de auto-ejecutar sin aprobación puntual la habilita el humano que configuró
    `Chat.permission_mode=auto` de antemano) y lo ejecuta inmediatamente contra el sandbox real,
    transicionando `proposed -> executed`/`failed` directo -- NUNCA pasa por `status=approved`.

    Firma estable: `create_and_execute_tool_run(db: Session, chat_id: str, tool_key: str,
    action_id: str, params: dict[str, Any] | None = None) -> ToolRun`.

    Levanta `LookupError` si `chat_id` no corresponde a un `Chat` existente -- en la práctica el
    loop ya tiene el `Chat` cargado en memoria (es quien resolvió `permission_mode` para decidir
    esta rama), así que este caso debería ser excepcional/defensivo.
    """
    chat = db.get(Chat, chat_id)
    if chat is None:
        raise LookupError(f"Chat {chat_id!r} not found")
    tool_run = propose_tool_run(db, chat, tool_key, action_id, params, triggered_by="llm")
    return execute_tool_run(db, tool_run)


__all__ = [
    "propose_tool_run",
    "execute_tool_run",
    "create_and_execute_tool_run",
]
