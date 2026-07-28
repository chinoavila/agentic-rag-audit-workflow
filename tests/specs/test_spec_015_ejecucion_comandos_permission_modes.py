from __future__ import annotations

import os

import pytest
from fastapi import status

from app.models.tool_catalog_entry import ToolCatalogEntry
from app.models.tool_run import ToolRun


def _seed_sandbox_example_tool(db_session) -> None:
    """Da de alta en el catálogo la entry `_sandbox_example` que ya trae, como ejemplo
    ilustrativo y determinístico, `app/agentic_core/tool_execution/allowlist.py` (Task 9):
    `argv_template=("/bin/echo", "{message}")`, `params=(enum "message" in {"ok","ping","pong"})`.
    No está seedeada por `app/main.py::_SEED_TOOL_CATALOG` (esas 3 tools no tienen `command`
    real), así que los tests que ejercitan el ciclo completo contra el sandbox real la insertan
    a mano.
    """
    db_session.add(
        ToolCatalogEntry(
            key="_sandbox_example",
            label="Sandbox example (test)",
            description="Entry ilustrativa de la allowlist real, ver allowlist.py",
            installed=True,
            actions=[{"id": "echo_message", "label": "Echo", "command": "internal:not_real"}],
        )
    )
    db_session.commit()


def _create_chat(client, permission_mode: str = "manual") -> str:
    resp = client.post("/api/chats", json={"title": "Chat de test spec-015"})
    assert resp.status_code == 201, resp.text
    chat_id = resp.json()["id"]
    if permission_mode != "manual":
        patch_resp = client.patch(f"/api/chats/{chat_id}", json={"permission_mode": permission_mode})
        assert patch_resp.status_code == 200, patch_resp.text
    return chat_id


# El sandbox real (`app/agentic_core/tool_execution/sandbox.py`) usa `resource.setrlimit`/
# `os.killpg` (POSIX-only) -- mismo guard que `tests/unit/test_tool_execution_sandbox.py`; el
# target real de despliegue es el contenedor Linux de `Dockerfile.backend`.
requires_posix = pytest.mark.skipif(
    os.name != "posix",
    reason="El sandbox usa resource.setrlimit/os.killpg (POSIX-only); target real: contenedor Linux.",
)


@pytest.mark.spec_015
class TestEjecucionComandosPermissionModes:
    """Spec-015: Ejecución de Comandos con Permission Modes de Chat y ToolRun (.ai/specs/audit/spec-015-ejecucion-comandos-permission-modes.md)"""

    # --- Sandboxing y Autorización (security-compliance) ---

    def test_command_execution_never_uses_shell_true_or_string_interpolation(self):
        pytest.skip("pending implementation: spec-015")

    def test_command_outside_allowlist_never_reaches_executed_status(self):
        pytest.skip("pending implementation: spec-015")

    def test_command_parameter_failing_schema_validation_is_rejected(self):
        pytest.skip("pending implementation: spec-015")

    def test_executed_subprocess_cannot_read_groq_api_key_or_database_url(self):
        pytest.skip("pending implementation: spec-015")

    def test_executed_subprocess_has_no_default_network_egress(self):
        pytest.skip("pending implementation: spec-015")

    def test_command_exceeding_timeout_is_killed_and_marked_failed_structured(self):
        pytest.skip("pending implementation: spec-015")

    def test_command_exceeding_resource_limits_is_marked_failed_structured(self):
        pytest.skip("pending implementation: spec-015")

    def test_nonzero_exit_code_never_propagates_as_raw_exception(self):
        pytest.skip("pending implementation: spec-015")

    def test_sandbox_applies_regardless_of_catalog_metadata_labeled_low_risk(self):
        pytest.skip("pending implementation: spec-015")

    def test_no_llm_invocable_path_mutates_chat_permission_mode(self):
        pytest.skip("pending implementation: spec-015")

    def test_chat_created_with_permission_mode_manual_by_default(self):
        pytest.skip("pending implementation: spec-015")

    def test_auto_mode_still_enforces_same_allowlist_and_resource_limits_as_manual(self):
        pytest.skip("pending implementation: spec-015")

    # --- Persistencia: ToolRun y Chat.permission_mode (backend-api) ---

    def test_tool_run_requires_chat_id_fk(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_valid_with_chat_case_id_null(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_valid_with_chat_case_id_set(self):
        pytest.skip("pending implementation: spec-015")

    @requires_posix
    def test_tool_run_command_resuelto_persists_resolved_argv_not_catalog_text(
        self, client, db_session
    ):
        """`command_resuelto` de una propuesta con entrada válida en la allowlist es el `argv`
        ya resuelto (ver `shlex.join` en `app/services/tool_run_execution.py`), nunca el texto
        descriptivo de `ToolCatalogEntry.actions[].command` (`"internal:not_real"`)."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client)

        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "proposed"
        assert body["command_resuelto"] == "/bin/echo ok"
        assert "internal:not_real" not in body["command_resuelto"]

    def test_tool_run_permission_mode_snapshot_frozen_at_proposal_time(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_permission_mode_snapshot_not_updated_when_chat_permission_mode_changes_later(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_status_enum_rejects_invalid_value(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_error_fields_null_unless_status_failed(self):
        pytest.skip("pending implementation: spec-015")

    @requires_posix
    def test_tool_run_error_code_restricted_to_security_compliance_set(self, client, db_session):
        """Aprobar una propuesta para `(tool_key, action_id)` fuera de la allowlist real
        transiciona a `status=failed` con `error_code="no_allowlist_entry"` -- dentro del set
        cerrado de spec-015, nunca un código inventado."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "accion_inexistente", "params": {}},
        )
        assert propose.status_code == 201, propose.text
        tool_run_id = propose.json()["id"]

        approve = client.patch(f"/api/tool-runs/{tool_run_id}", json={"status": "approved"})
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["status"] == "failed"
        assert body["error_code"] == "no_allowlist_entry"
        assert body["error_code"] in ("no_allowlist_entry", "timeout", "resource_limit_exceeded", "nonzero_exit")

    @requires_posix
    def test_tool_run_exit_code_null_for_non_nonzero_exit_errors(self, client, db_session):
        """`exit_code` queda `None` para un error `no_allowlist_entry` (no corresponde a un
        proceso real que haya terminado con un código de salida)."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "accion_inexistente", "params": {}},
        )
        tool_run_id = propose.json()["id"]

        approve = client.patch(f"/api/tool-runs/{tool_run_id}", json={"status": "approved"})
        body = approve.json()
        assert body["status"] == "failed"
        assert body["exit_code"] is None

    @requires_posix
    def test_tool_run_resolved_by_only_set_on_human_patch(self, client, db_session):
        """`resolved_by` es `None` en la propuesta (`status=proposed`) y se puebla recién con
        el `PATCH` humano de aprobación/rechazo."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        assert propose.json()["resolved_by"] is None
        tool_run_id = propose.json()["id"]

        approve = client.patch(f"/api/tool-runs/{tool_run_id}", json={"status": "approved"})
        assert approve.json()["resolved_by"] == "dev-user-0"

    def test_no_physical_delete_endpoint_exists_for_tool_runs(self, client, db_session):
        """No existe ningún método `DELETE` registrado para `/api/tool-runs/*` ni
        `/api/chats/*/tool-runs*` (append-only, spec-004/spec-015)."""
        from app.main import app

        delete_paths = {
            route.path
            for route in app.router.routes
            if hasattr(route, "methods") and "DELETE" in (route.methods or set())
        }
        assert not any("tool-run" in path for path in delete_paths)

        # Ninguna llamada DELETE sobre un ToolRun real existe como endpoint -- el intento
        # devuelve 405 (método no permitido para esa ruta) en vez de borrar.
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client)
        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        tool_run_id = propose.json()["id"]
        delete_attempt = client.delete(f"/api/tool-runs/{tool_run_id}")
        assert delete_attempt.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert db_session.get(ToolRun, tool_run_id) is not None

    def test_tool_run_created_at_immutable_after_creation(self):
        pytest.skip("pending implementation: spec-015")

    def test_chat_permission_mode_defaults_to_manual_on_create(self):
        pytest.skip("pending implementation: spec-015")

    def test_chat_out_exposes_permission_mode(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_to_auto(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_to_accept_edit(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_invalid_value_returns_422(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_works_with_case_id_null(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_works_with_case_id_set(self):
        pytest.skip("pending implementation: spec-015")

    def test_no_tool_or_llm_invocable_endpoint_can_mutate_permission_mode(self):
        pytest.skip("pending implementation: spec-015")

    def test_migration_adds_permission_mode_column_to_existing_chats_table(self):
        pytest.skip("pending implementation: spec-015")

    def test_chat_patch_rejects_unknown_field_extra_forbid(self):
        pytest.skip("pending implementation: spec-015")

    def test_project_tool_model_has_no_confirm_column(self):
        pytest.skip("pending implementation: spec-015")

    def test_project_tool_patch_rejects_confirm_field_extra_forbid(self):
        pytest.skip("pending implementation: spec-015")

    def test_project_tool_out_does_not_expose_confirm(self):
        pytest.skip("pending implementation: spec-015")

    def test_migration_drops_confirm_column_from_existing_project_tools_table(self):
        pytest.skip("pending implementation: spec-015")

    @requires_posix
    def test_patch_tool_run_approved_updates_status_and_sets_resolved_by(self, client, db_session):
        """Aprobar (`PATCH status=approved`) un `ToolRun` con entrada válida en la allowlist
        invoca el sandbox REAL y lo transiciona a `status=executed` (nunca se queda colgado en
        `approved`), poblando `resolved_by`/`triggered_by="human"`."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ping"}},
        )
        assert propose.status_code == 201, propose.text
        tool_run_id = propose.json()["id"]

        approve = client.patch(f"/api/tool-runs/{tool_run_id}", json={"status": "approved"})
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["status"] == "executed"
        assert body["exit_code"] == 0
        assert body["error_code"] is None
        assert body["triggered_by"] == "human"
        assert body["resolved_by"] == "dev-user-0"

        persisted = db_session.get(ToolRun, tool_run_id)
        assert persisted.status == "executed"

    @requires_posix
    def test_patch_tool_run_rejected_updates_status_and_sets_resolved_by(self, client, db_session):
        """Rechazar (`PATCH status=rejected`) nunca invoca el sandbox -- queda `status=rejected`
        sin `exit_code`/`error_code`, con `resolved_by` poblado."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "pong"}},
        )
        tool_run_id = propose.json()["id"]

        reject = client.patch(f"/api/tool-runs/{tool_run_id}", json={"status": "rejected"})
        assert reject.status_code == 200, reject.text
        body = reject.json()
        assert body["status"] == "rejected"
        assert body["exit_code"] is None
        assert body["error_code"] is None
        assert body["triggered_by"] == "human"
        assert body["resolved_by"] == "dev-user-0"

    @requires_posix
    def test_patch_tool_run_with_command_resuelto_edits_and_approves(self, client, db_session):
        """`PATCH` con `command_resuelto` editado persiste el texto editado para
        auditoría/visualización, pero la ejecución real sigue re-resolviendo el `argv` desde
        `(tool_key, action_id, params)` vía la allowlist -- nunca desde el texto libre editado
        (spec-015, punto 1)."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        propose = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        tool_run_id = propose.json()["id"]

        approve = client.patch(
            f"/api/tool-runs/{tool_run_id}",
            json={"status": "approved", "command_resuelto": "/bin/echo ok  # editado por un humano"},
        )
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["command_resuelto"] == "/bin/echo ok  # editado por un humano"
        # La ejecución real sigue basándose en los params originales (validados por la
        # allowlist), no en el texto editado -- por eso igual se ejecuta con éxito.
        assert body["status"] == "executed"
        assert body["exit_code"] == 0

    def test_get_tool_runs_by_chat_id_with_status_filter(self, client, db_session):
        """`GET /api/chats/{chat_id}/tool-runs?status=` lista propuestas de un chat, con filtro
        opcional por status."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="manual")

        for message in ("ok", "ping"):
            resp = client.post(
                f"/api/chats/{chat_id}/tool-runs",
                json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": message}},
            )
            assert resp.status_code == 201, resp.text

        all_runs = client.get(f"/api/chats/{chat_id}/tool-runs")
        assert all_runs.status_code == 200
        assert len(all_runs.json()) == 2
        assert all(run["status"] == "proposed" for run in all_runs.json())

        proposed_only = client.get(f"/api/chats/{chat_id}/tool-runs", params={"status": "proposed"})
        assert proposed_only.status_code == 200
        assert len(proposed_only.json()) == 2

        executed_only = client.get(f"/api/chats/{chat_id}/tool-runs", params={"status": "executed"})
        assert executed_only.status_code == 200
        assert executed_only.json() == []

    # --- Loop Agéntico (agentic-core) ---

    def test_loop_reads_permission_mode_from_chat_id_of_current_turn_not_per_tool_config(self):
        pytest.skip("pending implementation: spec-015")

    def test_permission_mode_snapshot_frozen_at_toolrun_insert_never_recalculated_after(self):
        pytest.skip("pending implementation: spec-015")

    def test_fixed_tools_without_real_command_bypass_toolrun_branching(self):
        pytest.skip("pending implementation: spec-015")

    def test_manual_mode_never_calls_execution_endpoint_creates_proposed_toolrun(self):
        pytest.skip("pending implementation: spec-015")

    def test_accept_edit_mode_creates_proposed_toolrun_and_pauses_turn_without_auto_execution(self):
        pytest.skip("pending implementation: spec-015")

    def test_auto_mode_with_human_origin_iteration_zero_executes_direct_proposed_to_executed(self):
        pytest.skip("pending implementation: spec-015")

    def test_auto_mode_with_tool_originated_proposal_iteration_one_plus_degrades_to_accept_edit(self):
        pytest.skip("pending implementation: spec-015")

    def test_document_triggered_proposal_never_resolves_to_auto(self):
        pytest.skip("pending implementation: spec-015")

    def test_result_of_earlier_tool_call_same_turn_never_resolves_to_auto(self):
        pytest.skip("pending implementation: spec-015")

    def test_triggered_by_is_set_server_side_and_ignores_llm_supplied_value(self):
        pytest.skip("pending implementation: spec-015")

    def test_failed_toolrun_never_auto_retried_by_loop(self):
        pytest.skip("pending implementation: spec-015")

    def test_failed_toolrun_error_returned_as_structured_tool_message_same_shape_as_spec_003(self):
        pytest.skip("pending implementation: spec-015")

    def test_llm_proposed_retry_after_failure_gets_independent_origin_verification(self):
        pytest.skip("pending implementation: spec-015")

    def test_execution_tool_declaration_passed_via_tools_param_not_system_prompt(self):
        pytest.skip("pending implementation: spec-015")

    def test_execution_result_wrapped_in_untrusted_context_before_returning_to_llm(self):
        pytest.skip("pending implementation: spec-015")

    def test_permission_mode_field_not_mutable_by_any_tool_or_endpoint_reachable_from_loop(self):
        pytest.skip("pending implementation: spec-015")

    # --- UI (chainlit-ui) ---

    def test_permission_mode_selector_visible_in_chat_header_react(self):
        pytest.skip("pending implementation: spec-015")

    def test_permission_mode_selector_available_for_standalone_and_case_chats(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_chat_permission_mode_updates_selector_and_reverts_on_error(self):
        pytest.skip("pending implementation: spec-015")

    def test_new_chat_selector_defaults_to_manual_and_patches_after_first_creation(self):
        pytest.skip("pending implementation: spec-015")

    def test_changing_permission_mode_mid_conversation_does_not_alter_existing_tool_run_cards_snapshot(self):
        pytest.skip("pending implementation: spec-015")

    def test_degraded_auto_tool_run_shows_explicit_badge_without_changing_selector_displayed_value(self):
        pytest.skip("pending implementation: spec-015")

    def test_ui_never_renders_raw_tool_catalog_entry_command_only_command_resuelto(self):
        pytest.skip("pending implementation: spec-015")

    def test_accept_edit_tool_run_shows_editable_command_resuelto_with_approve_reject_buttons(self):
        pytest.skip("pending implementation: spec-015")

    def test_accept_edit_tool_run_shows_read_only_command_when_sandbox_does_not_allow_variable_params(self):
        pytest.skip("pending implementation: spec-015")

    def test_manual_tool_run_shows_read_only_command_with_no_execute_or_approve_action(self):
        pytest.skip("pending implementation: spec-015")

    def test_manual_tool_run_command_resuelto_is_copyable_via_code_block(self):
        pytest.skip("pending implementation: spec-015")

    def test_approve_tool_run_sends_patch_and_renders_executed_result_with_output(self):
        pytest.skip("pending implementation: spec-015")

    def test_reject_tool_run_sends_patch_and_renders_rejected_state(self):
        pytest.skip("pending implementation: spec-015")

    def test_failed_tool_run_shows_structured_error_code_and_error_detail(self):
        pytest.skip("pending implementation: spec-015")

    def test_chainlit_chat_settings_widget_updates_permission_mode_via_direct_db_write(self):
        pytest.skip("pending implementation: spec-015")

    def test_chainlit_manual_tool_run_message_has_no_action_buttons(self):
        pytest.skip("pending implementation: spec-015")

    def test_chainlit_accept_edit_tool_run_offers_approve_edit_and_reject_actions(self):
        pytest.skip("pending implementation: spec-015")

    def test_chainlit_edit_and_approve_uses_askusermessage_pattern_consistent_with_new_project(self):
        pytest.skip("pending implementation: spec-015")

    def test_no_free_text_parsing_resolves_tool_run_approval_in_either_ui(self):
        pytest.skip("pending implementation: spec-015")


@pytest.mark.spec_015
class TestProposeToolRunEndpoint:
    """`POST /api/chats/{chat_id}/tool-runs` (Task 10 -- interfaz que `agentic_core`, Task 12,
    invocará cuando el LLM proponga ejecutar una acción con `command` real). No corresponde a
    ningún nombre de test case fijo de la spec (el bullet original de "Endpoints de API para
    ToolRun" solo listaba `PATCH`/`GET`; el `POST` es parte explícita del alcance de la Task 10
    del plan de migración) -- se cubre acá con nombres descriptivos propios.
    """

    def test_propose_creates_tool_run_in_proposed_status_never_executes(self, client, db_session):
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="auto")  # ni siquiera en auto ejecuta acá

        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "proposed"
        assert body["triggered_by"] == "llm"
        assert body["exit_code"] is None
        assert body["error_code"] is None

    def test_propose_freezes_permission_mode_snapshot_from_chat_at_insert_time(self, client, db_session):
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client, permission_mode="accept_edit")

        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {"message": "ok"}},
        )
        assert resp.json()["permission_mode_snapshot"] == "accept_edit"

    def test_propose_unknown_chat_returns_404_uniform_error_contract(self, client, db_session):
        _seed_sandbox_example_tool(db_session)
        resp = client.post(
            "/api/chats/chat-que-no-existe/tool-runs",
            json={"tool_key": "_sandbox_example", "action_id": "echo_message", "params": {}},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "chat_not_found"
        assert "detail" in body

    def test_propose_unknown_tool_key_returns_404(self, client):
        chat_id = _create_chat(client)
        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={"tool_key": "tool_que_no_existe", "action_id": "echo_message", "params": {}},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "tool_not_found"

    def test_propose_rejects_unknown_field_extra_forbid(self, client, db_session):
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client)
        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={
                "tool_key": "_sandbox_example",
                "action_id": "echo_message",
                "params": {"message": "ok"},
                "status": "executed",  # nunca aceptado del body -- server-side siempre
            },
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"

    def test_propose_does_not_accept_triggered_by_from_caller(self, client, db_session):
        """`ToolRunCreate` ni siquiera declara `triggered_by` -- un intento de colarlo es
        rechazado por `extra=\"forbid\"`, nunca silenciosamente ignorado ni aceptado."""
        _seed_sandbox_example_tool(db_session)
        chat_id = _create_chat(client)
        resp = client.post(
            f"/api/chats/{chat_id}/tool-runs",
            json={
                "tool_key": "_sandbox_example",
                "action_id": "echo_message",
                "params": {"message": "ok"},
                "triggered_by": "human",
            },
        )
        assert resp.status_code == 422
