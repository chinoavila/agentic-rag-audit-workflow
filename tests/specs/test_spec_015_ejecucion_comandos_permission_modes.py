import pytest


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

    def test_tool_run_command_resuelto_persists_resolved_argv_not_catalog_text(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_permission_mode_snapshot_frozen_at_proposal_time(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_permission_mode_snapshot_not_updated_when_chat_permission_mode_changes_later(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_status_enum_rejects_invalid_value(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_error_fields_null_unless_status_failed(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_error_code_restricted_to_security_compliance_set(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_exit_code_null_for_non_nonzero_exit_errors(self):
        pytest.skip("pending implementation: spec-015")

    def test_tool_run_resolved_by_only_set_on_human_patch(self):
        pytest.skip("pending implementation: spec-015")

    def test_no_physical_delete_endpoint_exists_for_tool_runs(self):
        pytest.skip("pending implementation: spec-015")

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

    def test_patch_tool_run_approved_updates_status_and_sets_resolved_by(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_tool_run_rejected_updates_status_and_sets_resolved_by(self):
        pytest.skip("pending implementation: spec-015")

    def test_patch_tool_run_with_command_resuelto_edits_and_approves(self):
        pytest.skip("pending implementation: spec-015")

    def test_get_tool_runs_by_chat_id_with_status_filter(self):
        pytest.skip("pending implementation: spec-015")

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
