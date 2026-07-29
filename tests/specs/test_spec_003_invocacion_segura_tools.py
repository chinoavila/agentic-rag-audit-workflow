"""Tests para spec-003: Invocación Segura de Tools de Auditoría.

Criterios de aceptación:
- Toda tool valida su input contra un schema explícito antes de ejecutar lógica de negocio.
- Una tool que falla retorna {"error": str, "code": str}, nunca deja propagar una excepción.
- El loop agéntico respeta MAX_TOOL_ITERATIONS y corta con un mensaje explícito.
- Tools de escritura (create_finding) son idempotentes ante reintentos con el mismo input.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

import app.tools.create_finding  # noqa: F401 - aseguran que el módulo esté en sys.modules
from app.agentic_core import loop as loop_module
from app.models.audit_case import AuditCase
from app.models.chat import Chat
from app.models.finding import Finding
from app.tools.create_finding import create_finding

# `app/tools/__init__.py` hace `from app.tools.create_finding import create_finding`, lo cual
# SOBREESCRIBE el atributo `app.tools.create_finding` (que apuntaba al submódulo) con la
# función del mismo nombre. `import app.tools.create_finding as X` resuelve vía esa misma
# cadena de atributos y por lo tanto también apunta a la función, no al submódulo -- hace
# falta ir directo a `sys.modules` para obtener el submódulo real y poder monkeypatchear sus
# funciones privadas.
create_finding_module = sys.modules["app.tools.create_finding"]


@pytest.mark.spec_003
class TestInvocacionSeguraTools:
    """Spec-003: Invocacion Segura de Tools de Auditoria (.ai/specs/audit/spec-003-invocacion-segura-tools.md)"""

    def test_tool_rejects_invalid_input_with_structured_error(self, db_session):
        """Un input que no cumple `CreateFindingInput` (evidence vacío) se rechaza con un
        error estructurado, sin tocar la DB.
        """
        case = AuditCase(id="case_spec003_a", name="Caso spec-003 a")
        db_session.add(case)
        db_session.commit()

        result = create_finding(
            {
                "case_id": case.id,
                "title": "Hallazgo sin evidencia",
                "description": "No debería crearse",
                "severity": "high",
                "evidence": [],  # min_length=1 en CreateFindingInput -> inválido
            },
            db=db_session,
        )

        assert result["code"] == "invalid_input"
        assert isinstance(result["error"], str) and result["error"]
        assert db_session.query(Finding).filter(Finding.case_id == case.id).count() == 0

    def test_tool_failure_returns_structured_error_not_raw_exception(self, db_session, monkeypatch):
        """Una falla inesperada durante la ejecución (no de validación de input) se traduce a
        `{"error": str, "code": "internal_error"}`: la tool nunca deja escapar la excepción
        cruda hacia el caller/LLM.
        """
        case = AuditCase(id="case_spec003_b", name="Caso spec-003 b")
        db_session.add(case)
        db_session.commit()

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("fallo inesperado simulado")

        monkeypatch.setattr(create_finding_module, "_find_existing_by_content_key", _boom)

        result = create_finding(
            {
                "case_id": case.id,
                "title": "Hallazgo que dispara excepción interna",
                "description": "desc",
                "severity": "medium",
                "evidence": [{"source": "doc.txt", "page": 1}],
            },
            db=db_session,
        )

        assert result["code"] == "internal_error"
        assert "fallo inesperado simulado" in result["error"]

    async def test_agent_loop_stops_at_max_tool_iterations(self, db_session, monkeypatch):
        """Si el LLM emite `tool_calls` en cada iteración sin nunca devolver una respuesta
        final, el loop corta exactamente en `MAX_TOOL_ITERATIONS` con `hit_max_iterations=True`
        y un mensaje explícito, en vez de iterar indefinidamente.
        """

        class _FakeFunction:
            def __init__(self, name: str, arguments: str) -> None:
                self.name = name
                self.arguments = arguments

        class _FakeToolCall:
            def __init__(self, call_id: str) -> None:
                self.id = call_id
                self.function = _FakeFunction("tool_que_no_existe", "{}")

        class _FakeMessage:
            def __init__(self, call_id: str) -> None:
                self.content = None
                self.tool_calls = [_FakeToolCall(call_id)]

        class _FakeChoice:
            def __init__(self, call_id: str) -> None:
                self.message = _FakeMessage(call_id)

        class _FakeResponse:
            def __init__(self, call_id: str) -> None:
                self.choices = [_FakeChoice(call_id)]

        call_counter = {"n": 0}

        class _FakeCompletions:
            async def create(self, **kwargs: Any) -> _FakeResponse:
                call_counter["n"] += 1
                return _FakeResponse(f"call_{call_counter['n']}")

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeAsyncClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        monkeypatch.setattr(loop_module, "get_client", lambda: _FakeAsyncClient())

        # spec-015 (agentic-core, Task 12): `run_agent_turn` ahora requiere `chat_id` -- un
        # `Chat` real es necesario para resolver `permission_mode` en la rama de tools con
        # `command` real, aunque este test no la ejercite (`tool_que_no_existe` no es una tool
        # elegible/dinámica de este turno, cae en el mismo camino `unknown_tool` de siempre).
        chat = Chat()
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        result = await loop_module.run_agent_turn(
            "buscá algo indefinidamente", [], db_session, chat_id=chat.id
        )

        assert result.hit_max_iterations is True
        assert call_counter["n"] == loop_module.MAX_TOOL_ITERATIONS
        assert len(result.tool_calls) == loop_module.MAX_TOOL_ITERATIONS
        assert str(loop_module.MAX_TOOL_ITERATIONS) in result.final_text

    def test_write_tool_is_idempotent_on_retry(self, db_session):
        """Reintentar `create_finding` con el mismo input (mismo case_id/title/evidence) no
        crea un segundo `Finding`: la segunda llamada devuelve `idempotent_hit=True` apuntando
        al mismo `finding_id`.
        """
        case = AuditCase(id="case_spec003_c", name="Caso spec-003 c")
        db_session.add(case)
        db_session.commit()

        tool_input = {
            "case_id": case.id,
            "title": "Hallazgo reintentado",
            "description": "Descripción original",
            "severity": "high",
            "evidence": [{"source": "doc.txt", "page": 3}],
        }

        first = create_finding(tool_input, db=db_session)
        assert "error" not in first
        assert first["idempotent_hit"] is False

        second = create_finding(dict(tool_input), db=db_session)
        assert "error" not in second
        assert second["idempotent_hit"] is True
        assert second["finding_id"] == first["finding_id"]

        assert db_session.query(Finding).filter(Finding.case_id == case.id).count() == 1
