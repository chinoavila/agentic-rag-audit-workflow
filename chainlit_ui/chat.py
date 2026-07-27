"""
Chainlit conversational UI for Agentic-RAG Audit Workflow (task 6, `chainlit-ui`).

Entrega el primer slice end-to-end de la UI real: crea un `AuditCase` por sesión, delega
cada mensaje del usuario en `app.agentic_core.loop.run_agent_turn`, muestra cada tool call
con `cl.Step`, da efecto de streaming sobre la respuesta final y expone acciones tipadas de
aprobar/rechazar para hallazgos `high`/`critical` en `pending_review` (spec-006).

Decisiones de diseño (para que `security-compliance`, próxima task, no tenga que
re-descubrirlas leyendo el código):

1. **Streaming (`.ai/skills/chainlit/SKILL.md` regla 1)**: `run_agent_turn` NO es un
   generador async -- devuelve `final_text` completo recién cuando el loop de tool-calling
   termina (el LLM no puede "hablar" mientras todavía puede emitir más `tool_calls`; un
   streaming token-a-token real requeriría que `agentic_core.loop` yield-eara deltas del
   proveedor, lo cual es un refactor de `agentic-core`, fuera de alcance de este slice). Acá
   compensamos troceando `final_text` ya completo por palabras y usando
   `cl.Message(content="") + stream_token(...)` para el efecto de "escritura en vivo" en vez
   de mandar la respuesta de una sola vez con `cl.Message(content=final_text).send()`. Sigue
   siendo la Quick Rule (usa `stream_token`), pero NO es streaming real del LLM: queda
   documentado para que no se asuma latencia/UX de streaming real en la demo.
2. **Visibilidad del razonamiento (regla 2)**: cada `ToolCallRecord` de
   `result.tool_calls` se renderiza en su propio `cl.Step(name=tool_name, type="tool")` con
   input/output, nunca mezclado como texto plano en el mensaje del asistente.
3. **Aislamiento de sesión (regla 3, spec-007)**: `case_id` y `conversation_history` viven
   únicamente en `cl.user_session` (nunca en una variable de módulo). Las únicas constantes
   de módulo de este archivo son valores fijos e inmutables compartidos por diseño (nombre
   de la tool, id de usuario dev fijo), no estado de ninguna sesión.
4. **Actions tipadas (regla 4, spec-006)**: aprobar/rechazar un hallazgo `high`/`critical`
   en `pending_review` es siempre un `cl.Action` explícito (`approve_finding`/
   `reject_finding`), nunca texto libre interpretado como "sí, apruébalo". Mismo patrón para
   informes generados por `generate_report` (spec-012): TODO informe queda en
   `pending_review` (sin excepción por severidad, a diferencia de `findings`) y se aprueba/
   rechaza vía `approve_report`/`reject_report`.
5. **Chat profiles (regla 5)**: no aplica en este slice -- hay un único modo de operación
   (un asistente de auditoría). Si en el futuro se agrega un modo "solo consulta" (sin
   `create_finding` habilitada), ahí sí corresponde `@cl.set_chat_profiles`.
6. **Acceso a datos (`backend-api` task 2)**: en vez de hacer HTTP interno contra
   `POST /api/audit-cases` / `PATCH /api/findings/{id}`, esta UI reusa la sesión SQLAlchemy y
   llama directamente la lógica de `app/routers/*.py` (o el modelo ORM cuando no hay lógica
   de negocio relevante), igual patrón que ya usa `app/tools/create_finding.py`
   (`audit-tools`, task 4). `chainlit` y `backend` corren en contenedores separados
   (`docker-compose.yml`) pero comparten el mismo volumen `sqlite_data`
   (`AUDIT_DATABASE_URL=sqlite:////data/audit_trail.db`), así que ambos procesos leen/escriben la
   misma base sin problema de consistencia para este slice.
7. **Auth (spec-007, incompleto a propósito en este slice)**: `app/deps.py::get_current_user`
   es un stub que siempre resuelve al mismo usuario fijo de desarrollo (`dev-user-0`), sin
   leer ningún token/cookie. Esta UI NO agrega `@cl.password_auth_callback` ni ningún login
   real: usa el comportamiento por defecto de Chainlit (sesión anónima, sin credenciales
   hardcodeadas de "producción") y reusa el mismo id de usuario dev fijo para `approved_by`.
   Mientras el backend siga con ese stub, dos pestañas de Chainlit abiertas en paralelo
   tienen `case_id`/`conversation_history` aislados entre sí (regla 3 arriba), pero
   *comparten* la misma identidad de "usuario auditor humano" a nivel de negocio -- no hay
   aislamiento de datos por usuario real todavía. Cerrar ese gap (spec-007 completo:
   autenticación real + filtrar casos/hallazgos por usuario) queda para
   `security-compliance` + `backend-api`, tal como ya lo documenta `app/deps.py`.
"""

from __future__ import annotations

import json

import chainlit as cl
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agentic_core.loop import AgentTurnResult, ToolCallRecord, run_agent_turn
from app.agentic_core.tools_registry import search_evidence
from app.db import SessionLocal
from app.deps import get_current_user
from app.models.audit_case import AuditCase
from app.routers.findings import patch_finding
from app.routers.reports import patch_report
from app.schemas.finding import HIGH_RISK_SEVERITIES, FindingPatch
from app.schemas.report import ReportPatch

__version__ = "0.3.0"

# Catálogo de tools mostrado en el sidebar (spec-014). Estático por ahora -- se reemplaza por
# `app/agentic_core/tool_catalog.py` (Fase 1 del plan de sidebar) cuando exista, que va a ser
# la única fuente de verdad tanto para esto como para `AGENT_TOOL_SPECS`/`TOOL_DISPATCH`.
# `runnable=True` solo en tools sin campos `list[object]` requeridos en su input_schema
# (decisión de diseño ya tomada: `create_finding`/`generate_report` quedan chat-only por
# ahora, ver plan de sidebar).
TOOLS_SIDEBAR_CATALOG: list[dict] = [
    {
        "name": "search_evidence",
        "label": "Buscar evidencia",
        "description": "Busca evidencia relevante en los documentos indexados (RAG).",
        "runnable": True,
    },
    {
        "name": "create_finding",
        "label": "Registrar hallazgo",
        "description": "Registra un hallazgo de auditoría con evidencia citada.",
        "runnable": False,
    },
    {
        "name": "generate_report",
        "label": "Generar informe",
        "description": "Genera un informe de auditoría desde una plantilla.",
        "runnable": False,
    },
]

# Identidad fija de desarrollo usada para `approved_by` al resolver una Action de
# aprobación/rechazo (ver punto 7 del docstring del módulo). Es un valor constante e
# inmutable, no estado de sesión -- no viola la regla 3 (aislamiento de sesión): todas las
# sesiones de Chainlit comparten a propósito este mismo valor porque `backend-api` todavía no
# distingue usuarios reales (`get_current_user` es un stub fijo). Reemplazar cuando
# `security-compliance` implemente auth real.
DEV_APPROVER_ID = "dev-user-0"


# ---------------------------------------------------------------------------
# Inicialización de sesión
# ---------------------------------------------------------------------------


def _create_default_audit_case(db: Session) -> AuditCase:
    """Crea el primer `AuditCase` ("proyecto") cuando todavía no existe ninguno.

    Ver punto 6 del docstring del módulo: acceso directo a la sesión SQLAlchemy en vez de un
    HTTP call interno a `POST /api/audit-cases`.
    """
    case = AuditCase(name="Proyecto inicial", status="open")
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _list_audit_cases(db: Session) -> list[AuditCase]:
    """Todos los proyectos existentes, más reciente primero (para listarlos en el sidebar)."""
    return db.query(AuditCase).order_by(AuditCase.created_at.desc()).all()


def _sidebar_props(db: Session, active_case_id: str) -> dict:
    cases = _list_audit_cases(db)
    return {
        "activeCaseId": active_case_id,
        "projects": [{"id": c.id, "name": c.name, "status": c.status} for c in cases],
        "tools": TOOLS_SIDEBAR_CATALOG,
    }


async def _refresh_sidebar(db: Session, active_case_id: str) -> None:
    """Redibuja el sidebar (`public/elements/Sidebar.jsx`) con el estado actual de proyectos.

    Se llama después de cualquier acción que cambie la lista de proyectos o el proyecto
    activo (crear, cambiar) para que el resaltado y el listado queden consistentes.
    """
    await cl.ElementSidebar.set_title("Proyectos y herramientas")
    await cl.ElementSidebar.set_elements(
        [cl.CustomElement(name="Sidebar", props=_sidebar_props(db, active_case_id))]
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    """Inicializa la sesión de chat: activa un proyecto y muestra el sidebar de
    proyectos/herramientas.

    Si ya existen proyectos (`AuditCase`), esta sesión arranca sobre el más reciente en vez de
    crear uno nuevo cada vez -- el sidebar (`switch_project`/`new_project`) es la forma de
    cambiar de proyecto o crear uno, mismo patrón que Claude Desktop/ChatGPT/Gemini.

    Aislamiento de sesión (regla 3 / spec-007): `case_id` y `conversation_history` se guardan
    únicamente en `cl.user_session`, que Chainlit aísla por conexión -- dos usuarios (o dos
    pestañas) nunca comparten ni pisan el `case_id`/historial del otro.

    Esta función abre y cierra su propia `Session` de SQLAlchemy de vida corta (ver
    `on_message` para el manejo de sesión del resto del ciclo de vida del chat).
    """
    db = SessionLocal()
    try:
        cases = _list_audit_cases(db)
        case = cases[0] if cases else _create_default_audit_case(db)

        cl.user_session.set("case_id", case.id)
        cl.user_session.set("conversation_history", [])

        await _refresh_sidebar(db, case.id)
    finally:
        db.close()

    await cl.Message(
        content=(
            "Bienvenido a Agentic-RAG Audit Workflow.\n\n"
            f"Proyecto activo: `{case.name}` (`{case.id}`). Usá el sidebar para crear un "
            "proyecto nuevo, cambiar a otro existente, o ejecutar una herramienta "
            "explícitamente.\n\n"
            "Pedime que busque evidencia sobre algún tema en los documentos indexados, o que "
            "registre un hallazgo de auditoría a partir de esa evidencia."
        )
    ).send()


# ---------------------------------------------------------------------------
# Acciones del sidebar: proyectos (spec-017) y ejecución explícita de tools (spec-014)
# ---------------------------------------------------------------------------


@cl.action_callback("new_project")
async def on_new_project(action: cl.Action) -> None:
    """Crea un proyecto nuevo (`callAction` desde el botón "+ Nuevo proyecto" del sidebar) y
    lo activa para esta sesión.
    """
    response = await cl.AskUserMessage(
        content="¿Cómo se llama el proyecto nuevo?", timeout=120
    ).send()
    name = (response or {}).get("output", "").strip() if response else ""
    if not name:
        await cl.Message(content="Creación de proyecto cancelada (sin nombre).").send()
        return

    db = SessionLocal()
    try:
        case = AuditCase(name=name, status="open")
        db.add(case)
        db.commit()
        db.refresh(case)

        cl.user_session.set("case_id", case.id)
        cl.user_session.set("conversation_history", [])

        await _refresh_sidebar(db, case.id)
    finally:
        db.close()

    await cl.Message(content=f"Proyecto `{case.name}` creado y activado.").send()


@cl.action_callback("switch_project")
async def on_switch_project(action: cl.Action) -> None:
    """Cambia el proyecto activo de esta sesión (click en un item de la lista del sidebar)."""
    case_id = (action.payload or {}).get("case_id")
    if not case_id or case_id == cl.user_session.get("case_id"):
        return

    db = SessionLocal()
    try:
        case = db.get(AuditCase, case_id)
        if case is None:
            await cl.Message(content="Ese proyecto ya no existe.").send()
            return

        cl.user_session.set("case_id", case.id)
        # TODO(spec-017, `CaseTurn`): reponer el historial persistido de este proyecto en vez
        # de arrancar en blanco -- ese modelo todavía no existe (ver plan de sidebar, Fase 1).
        cl.user_session.set("conversation_history", [])

        await _refresh_sidebar(db, case.id)
    finally:
        db.close()

    await cl.Message(content=f"Proyecto activo: `{case.name}`.").send()


@cl.action_callback("invoke_tool_explicit")
async def on_invoke_tool_explicit(action: cl.Action) -> None:
    """Ejecuta una tool explícitamente desde el sidebar, sin pasar por decisión del LLM
    (spec-014). Por ahora solo `search_evidence` es `runnable` en `TOOLS_SIDEBAR_CATALOG`
    (las tools con campos `list[object]` requeridos quedan chat-only, ver plan de sidebar).
    """
    tool_name = (action.payload or {}).get("tool_name")
    if tool_name != "search_evidence":
        await cl.Message(
            content=(
                f"`{tool_name}` todavía no se puede ejecutar desde el sidebar -- por ahora "
                "pedíselo al asistente en el chat."
            )
        ).send()
        return

    response = await cl.AskUserMessage(
        content="¿Qué querés buscar en los documentos indexados?", timeout=120
    ).send()
    query = (response or {}).get("output", "").strip() if response else ""
    if not query:
        await cl.Message(content="Búsqueda cancelada (sin consulta).").send()
        return

    tool_output = search_evidence({"query": query})
    record = ToolCallRecord(
        tool_name="search_evidence", tool_input={"query": query}, tool_output=tool_output
    )
    await _render_tool_call_step(record)


# ---------------------------------------------------------------------------
# Turno de mensaje: delega en agentic-core, nunca contiene lógica de negocio de auditoría
# ---------------------------------------------------------------------------


def _stream_chunks(text: str) -> list[str]:
    """Trocea `final_text` (ya completo) en fragmentos por palabra para el efecto de
    streaming. Ver punto 1 del docstring del módulo: esto NO es streaming real del LLM.
    """
    if not text:
        return [""]
    words = text.split(" ")
    return [f"{word} " for word in words[:-1]] + [words[-1]]


def _format_tool_input(tool_input: dict) -> str:
    return json.dumps(tool_input, ensure_ascii=False, indent=2)


def _format_search_evidence_output(tool_output: dict) -> str:
    if "error" in tool_output:
        return f"Error: {tool_output['error']} (code={tool_output.get('code')})"
    chunks = tool_output.get("chunks") or []
    if tool_output.get("insufficient_evidence") or not chunks:
        return "insufficient_evidence=true: no se encontró evidencia suficientemente relevante."
    lines = ["Citas recuperadas:"]
    for chunk in chunks:
        lines.append(
            f"- {chunk['source']} (página {chunk['page']}), "
            f"similitud={chunk['similarity']:.3f}"
        )
    return "\n".join(lines)


def _format_create_finding_output(tool_output: dict) -> str:
    if "error" in tool_output:
        return f"Error: {tool_output['error']} (code={tool_output.get('code')})"
    idempotent_note = " (idempotent hit: ya existía)" if tool_output.get("idempotent_hit") else ""
    return (
        f"finding_id={tool_output['finding_id']}\n"
        f"severity={tool_output['severity']}\n"
        f"risk_score={tool_output['risk_score']}\n"
        f"status={tool_output['status']}{idempotent_note}"
    )


def _format_generate_report_output(tool_output: dict) -> str:
    if "error" in tool_output:
        detail = f"Error: {tool_output['error']} (code={tool_output.get('code')})"
        rubric_results = tool_output.get("rubric_results")
        if rubric_results:
            failed_checks = [c for c in rubric_results.get("checks", []) if not c["passed"]]
            for check in failed_checks:
                detail += f"\n- [{check['name']}] {check['detail']}"
        return detail
    return (
        f"report_id={tool_output['report_id']}\n"
        f"template_id={tool_output['template_id']}\n"
        f"status={tool_output['status']}\n"
        f"blob_path={tool_output['blob_path']}"
    )


async def _render_tool_call_step(record: ToolCallRecord) -> None:
    """Renderiza un `ToolCallRecord` en su propio `cl.Step` (regla 2: nunca ocultarlo como
    texto plano mezclado con la respuesta del asistente).
    """
    async with cl.Step(name=record.tool_name, type="tool") as step:
        step.input = _format_tool_input(record.tool_input)
        if record.tool_name == "search_evidence":
            step.output = _format_search_evidence_output(record.tool_output)
        elif record.tool_name == "create_finding":
            step.output = _format_create_finding_output(record.tool_output)
        elif record.tool_name == "generate_report":
            step.output = _format_generate_report_output(record.tool_output)
        else:
            step.output = json.dumps(record.tool_output, ensure_ascii=False, indent=2)


async def _maybe_offer_approval_actions(tool_calls: list[ToolCallRecord]) -> None:
    """Ofrece Actions de aprobar/rechazar para cada `create_finding` que haya producido un
    hallazgo `high`/`critical` en `pending_review` (spec-006, regla 4), y para cada
    `generate_report` que haya persistido un informe (siempre `pending_review`: todo informe
    requiere aprobación humana antes de `published`, spec-006 aplicado a reportes).
    """
    for record in tool_calls:
        output = record.tool_output
        if "error" in output:
            continue

        if (
            record.tool_name == "create_finding"
            and output.get("severity") in HIGH_RISK_SEVERITIES
            and output.get("status") == "pending_review"
        ):
            finding_id = output["finding_id"]
            await cl.Message(
                content=(
                    f"El hallazgo `{finding_id}` (severity={output['severity']}) requiere "
                    "aprobación humana explícita antes de poder marcarse como `final` "
                    "(spec-006, human-in-the-loop). Elegí una acción:"
                ),
                actions=[
                    cl.Action(
                        name="approve_finding",
                        payload={"finding_id": finding_id},
                        label="Aprobar hallazgo",
                    ),
                    cl.Action(
                        name="reject_finding",
                        payload={"finding_id": finding_id},
                        label="Rechazar hallazgo",
                    ),
                ],
            ).send()
        elif record.tool_name == "generate_report" and output.get("status") == "pending_review":
            report_id = output["report_id"]
            await cl.Message(
                content=(
                    f"El informe `{report_id}` ({output['title']!r}) requiere aprobación "
                    "humana explícita antes de poder publicarse (spec-006, human-in-the-loop "
                    "aplicado a reportes). Elegí una acción:"
                ),
                actions=[
                    cl.Action(
                        name="approve_report",
                        payload={"report_id": report_id},
                        label="Aprobar informe",
                    ),
                    cl.Action(
                        name="reject_report",
                        payload={"report_id": report_id},
                        label="Rechazar informe",
                    ),
                ],
            ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Procesa un mensaje del usuario delegando por completo en `run_agent_turn`.

    Este handler no contiene lógica de negocio de auditoría (guía completa del skill): solo
    lee/escribe `cl.user_session`, llama al loop de `agentic-core` y renderiza el resultado.

    Manejo de sesión de DB: se abre y cierra una `Session` nueva por turno de mensaje (en vez
    de mantener una sesión abierta durante toda la vida del chat). Se eligió así para evitar
    conexiones SQLite de larga vida asociadas a una sesión de usuario que puede quedar
    inactiva por horas; el costo de reabrir la sesión en cada mensaje es despreciable para
    SQLite local. `run_agent_turn` recibe esa sesión y la reenvía tal cual a `create_finding`.
    """
    conversation_history: list[dict] = cl.user_session.get("conversation_history") or []

    db = SessionLocal()
    try:
        result: AgentTurnResult = await run_agent_turn(message.content, conversation_history, db)
    finally:
        db.close()

    cl.user_session.set("conversation_history", result.conversation_history)

    # Regla 2: cada tool call se muestra en su propio Step, ANTES del mensaje final, en el
    # mismo orden en que se ejecutó.
    for record in result.tool_calls:
        await _render_tool_call_step(record)

    # Regla 1 (compensada, ver punto 1 del docstring del módulo): troceo por palabra sobre
    # `final_text` ya completo en vez de `cl.Message(content=final_text).send()`.
    msg = cl.Message(content="")
    await msg.send()
    for chunk in _stream_chunks(result.final_text):
        await msg.stream_token(chunk)
    await msg.update()

    if result.hit_max_iterations:
        await cl.Message(
            content=(
                "AVISO: este turno se cortó porque el agente alcanzó el límite de "
                "iteraciones de tool-calling sin llegar a una respuesta final. Revisá los "
                "pasos de arriba -- puede que necesites reformular el pedido o pedir "
                "explícitamente que continúe en un nuevo mensaje."
            )
        ).send()

    await _maybe_offer_approval_actions(result.tool_calls)


# ---------------------------------------------------------------------------
# Actions de aprobación humana (spec-006)
# ---------------------------------------------------------------------------


async def _resolve_finding_action(action: cl.Action, *, approve: bool) -> None:
    """Ejecuta la transición de un hallazgo tras un click en `approve_finding`/
    `reject_finding`, llamando directamente `app.routers.findings.patch_finding` (ver punto 6
    del docstring del módulo) en vez de un HTTP call interno.
    """
    finding_id = (action.payload or {}).get("finding_id")
    if not finding_id:
        await cl.Message(content="Acción inválida: falta `finding_id` en el payload.").send()
        return

    target_status = "final" if approve else "rejected"

    try:
        patch_payload = FindingPatch(status=target_status, approved_by=DEV_APPROVER_ID)
    except ValidationError:
        # Gap conocido, documentado acá a propósito para `backend-api`/`security-compliance`:
        # `FindingStatus` (app/schemas/finding.py) es `Literal["draft", "pending_review",
        # "final"]` -- todavía NO incluye "rejected", aunque spec-006 pide explícitamente que
        # rechazar marque `status=rejected` preservando el registro. `chainlit-ui` no puede
        # resolver esto sin tocar app/schemas/ (fuera de su scope en esta task), así que en
        # vez de fallar en silencio o hackear un status inválido, se lo avisamos al humano.
        await cl.Message(
            content=(
                f"No se pudo rechazar el hallazgo `{finding_id}`: el backend todavía no "
                'soporta status="rejected" (falta en el Literal `FindingStatus`). Este es un '
                "gap conocido de `backend-api` respecto al acceptance criteria de spec-006 "
                '("Rechazar un hallazgo en pending_review lo marca superseded_by/'
                'status=rejected"), a resolver en una próxima task -- no requiere cambios en '
                "chainlit-ui."
            )
        ).send()
        return

    db = SessionLocal()
    try:
        try:
            finding = patch_finding(
                finding_id,
                patch_payload,
                db=db,
                current_user=get_current_user(),
            )
        except HTTPException as exc:
            detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail
            await cl.Message(
                content=f"No se pudo procesar la acción sobre `{finding_id}`: {detail}"
            ).send()
            return
    finally:
        db.close()

    await action.remove()
    verb = "aprobado" if approve else "rechazado"
    await cl.Message(
        content=(
            f"Hallazgo `{finding.id}` {verb}.\n"
            f"status={finding.status}, approved_by={finding.approved_by}, "
            f"approved_at={finding.approved_at}"
        )
    ).send()


@cl.action_callback("spike_ping")
async def on_spike_ping(action: cl.Action) -> None:
    """Handler del spike descartable de Fase 0 (ver docstring en `on_chat_start`):
    confirma que un click en el CustomElement del sidebar hace round-trip real a Python
    vía `callAction`. Se borra junto con `_Spike.jsx` una vez confirmado.
    """
    await cl.Message(content=f"spike_ping recibido: payload={action.payload!r}").send()


@cl.action_callback("approve_finding")
async def on_approve_finding(action: cl.Action) -> None:
    await _resolve_finding_action(action, approve=True)


@cl.action_callback("reject_finding")
async def on_reject_finding(action: cl.Action) -> None:
    await _resolve_finding_action(action, approve=False)


# ---------------------------------------------------------------------------
# Actions de aprobación humana para reportes (spec-006 aplicado a reportes, spec-011/spec-012)
# ---------------------------------------------------------------------------


async def _resolve_report_action(action: cl.Action, *, approve: bool) -> None:
    """Ejecuta la transición de un reporte tras un click en `approve_report`/
    `reject_report`, llamando directamente `app.routers.reports.patch_report` (ver punto 6
    del docstring del módulo) en vez de un HTTP call interno. A diferencia de
    `_resolve_finding_action`, acá `status="rejected"` siempre está soportado (`ReportStatus`
    lo incluye desde el diseño inicial de `app/schemas/report.py`, sin el gap histórico que
    tuvo `FindingStatus`).
    """
    report_id = (action.payload or {}).get("report_id")
    if not report_id:
        await cl.Message(content="Acción inválida: falta `report_id` en el payload.").send()
        return

    target_status = "published" if approve else "rejected"
    patch_payload = ReportPatch(status=target_status, approved_by=DEV_APPROVER_ID)

    db = SessionLocal()
    try:
        try:
            report = patch_report(
                report_id,
                patch_payload,
                db=db,
                current_user=get_current_user(),
            )
        except HTTPException as exc:
            detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else exc.detail
            await cl.Message(
                content=f"No se pudo procesar la acción sobre `{report_id}`: {detail}"
            ).send()
            return
    finally:
        db.close()

    await action.remove()
    verb = "aprobado" if approve else "rechazado"
    await cl.Message(
        content=(
            f"Informe `{report.id}` {verb}.\n"
            f"status={report.status}, approved_by={report.approved_by}, "
            f"approved_at={report.approved_at}"
        )
    ).send()


@cl.action_callback("approve_report")
async def on_approve_report(action: cl.Action) -> None:
    await _resolve_report_action(action, approve=True)


@cl.action_callback("reject_report")
async def on_reject_report(action: cl.Action) -> None:
    await _resolve_report_action(action, approve=False)
