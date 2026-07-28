"""Tests unitarios REALES (no skipeados) de `app/services/tool_run_execution.py` -- Task 10
del plan de migración (spec-015): conecta `ToolRun` (persistencia, Task 8) con el sandbox real
(`app/agentic_core/tool_execution/`, Task 9).

DB de test aislada (sqlite:///:memory: + StaticPool), mismo patrón que
`tests/unit/test_tool_eligibility.py` (este directorio no tiene conftest propio).

Usa la entry `_sandbox_example`/`echo_message` que ya deja `allowlist.py` (Task 9) como caso
determinístico end-to-end: `argv_template=("/bin/echo", "{message}")`, único parámetro
`message` validado por enum (`ok`/`ping`/`pong`).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.chat import Chat
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.models.tool_run import ToolRun
from app.services.tool_run_execution import (
    create_and_execute_tool_run,
    execute_tool_run,
    propose_tool_run,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "El sandbox usa resource.setrlimit/os.killpg (POSIX-only); el target real de "
        "despliegue es el contenedor Linux de Dockerfile.backend."
    ),
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_sandbox_example_catalog_entry(db: Session) -> None:
    db.add(
        ToolCatalogEntry(
            key="_sandbox_example",
            label="Sandbox example (test)",
            description="",
            installed=True,
            actions=[{"id": "echo_message", "label": "Echo", "command": "internal:not_real"}],
        )
    )
    db.commit()


def _chat(db: Session, permission_mode: str = "manual") -> Chat:
    chat = Chat(permission_mode=permission_mode)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


class TestProposeToolRun:
    def test_propose_creates_proposed_status_never_executes(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="auto")  # aunque el chat esté en auto, propose NUNCA ejecuta

        tool_run = propose_tool_run(
            db, chat, "_sandbox_example", "echo_message", {"message": "ok"}, triggered_by="llm"
        )

        assert tool_run.status == "proposed"
        assert tool_run.exit_code is None
        assert tool_run.error_code is None
        assert tool_run.resolved_by is None
        assert tool_run.triggered_by == "llm"

    def test_propose_freezes_permission_mode_snapshot_from_chat(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="accept_edit")

        tool_run = propose_tool_run(db, chat, "_sandbox_example", "echo_message", {"message": "ok"})
        assert tool_run.permission_mode_snapshot == "accept_edit"

        # Cambiar Chat.permission_mode DESPUÉS no debe recalcular el snapshot ya persistido.
        chat.permission_mode = "manual"
        db.commit()
        db.refresh(tool_run)
        assert tool_run.permission_mode_snapshot == "accept_edit"

    def test_propose_command_resuelto_reflects_resolved_argv_when_entry_exists(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db)

        tool_run = propose_tool_run(db, chat, "_sandbox_example", "echo_message", {"message": "pong"})
        assert tool_run.command_resuelto == "/bin/echo pong"

    def test_propose_command_resuelto_is_descriptive_placeholder_when_no_allowlist_entry(
        self, db: Session
    ):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db)

        tool_run = propose_tool_run(db, chat, "_sandbox_example", "accion_inexistente", {})
        assert tool_run.status == "proposed"  # la propuesta igual se crea
        assert "sin resolver" in tool_run.command_resuelto


class TestExecuteToolRun:
    def test_execute_valid_entry_transitions_to_executed(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="accept_edit")
        tool_run = propose_tool_run(db, chat, "_sandbox_example", "echo_message", {"message": "ok"})

        result = execute_tool_run(db, tool_run)

        assert result.status == "executed"
        assert result.exit_code == 0
        assert result.error_code is None
        assert result.error_detail is None

    def test_execute_missing_allowlist_entry_transitions_to_failed_structured(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db)
        tool_run = propose_tool_run(db, chat, "_sandbox_example", "accion_inexistente", {})

        result = execute_tool_run(db, tool_run)

        assert result.status == "failed"
        assert result.error_code == "no_allowlist_entry"
        assert result.exit_code is None

    def test_execute_invalid_param_transitions_to_failed_no_allowlist_entry(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db)
        tool_run = propose_tool_run(
            db, chat, "_sandbox_example", "echo_message", {"message": "not_a_valid_enum_choice"}
        )

        result = execute_tool_run(db, tool_run)

        assert result.status == "failed"
        assert result.error_code == "no_allowlist_entry"

    def test_execute_never_raises_raw_exception_on_unexpected_tool_key(self, db: Session):
        chat = _chat(db)
        # No hay fila en ToolCatalogEntry ni en la allowlist para esta key -- igual nunca debe
        # lanzar una excepción cruda (spec-003 regla 2, aplicado a ToolRun).
        tool_run = ToolRun(
            chat_id=chat.id,
            tool_key="tool_que_no_existe",
            action_id="accion_que_no_existe",
            command_resuelto="placeholder",
            params_json="{}",
            permission_mode_snapshot=chat.permission_mode,
            status="proposed",
            triggered_by="llm",
        )
        db.add(tool_run)
        db.commit()

        result = execute_tool_run(db, tool_run)
        assert result.status == "failed"
        assert result.error_code == "no_allowlist_entry"


class TestCreateAndExecuteToolRunDirectPath:
    """Contrato hacia agentic-core (Task 12): camino directo `auto` con origen verificado."""

    def test_direct_path_never_leaves_status_approved_goes_straight_to_executed(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="auto")

        tool_run = create_and_execute_tool_run(
            db, chat.id, "_sandbox_example", "echo_message", {"message": "ping"}
        )

        assert tool_run.status == "executed"
        assert tool_run.exit_code == 0
        assert tool_run.permission_mode_snapshot == "auto"
        assert tool_run.triggered_by == "llm"
        assert tool_run.resolved_by is None  # nunca hubo un PATCH humano en este camino

    def test_direct_path_failure_reaches_failed_never_stuck_mid_transition(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="auto")

        tool_run = create_and_execute_tool_run(
            db, chat.id, "_sandbox_example", "accion_inexistente", {}
        )

        assert tool_run.status == "failed"
        assert tool_run.error_code == "no_allowlist_entry"

    def test_direct_path_persists_single_tool_run_row_queryable_after(self, db: Session):
        _seed_sandbox_example_catalog_entry(db)
        chat = _chat(db, permission_mode="auto")

        tool_run = create_and_execute_tool_run(
            db, chat.id, "_sandbox_example", "echo_message", {"message": "ok"}
        )

        rows = db.query(ToolRun).filter(ToolRun.chat_id == chat.id).all()
        assert len(rows) == 1
        assert rows[0].id == tool_run.id
        assert rows[0].status == "executed"

    def test_direct_path_unknown_chat_id_raises_lookup_error(self, db: Session):
        with pytest.raises(LookupError):
            create_and_execute_tool_run(db, "chat-que-no-existe", "_sandbox_example", "echo_message", {})
