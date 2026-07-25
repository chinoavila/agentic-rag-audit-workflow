import pytest


@pytest.mark.spec_003
class TestInvocacionSeguraTools:
    """Spec-003: Invocacion Segura de Tools de Auditoria (.ai/specs/audit/spec-003-invocacion-segura-tools.md)"""

    def test_tool_rejects_invalid_input_with_structured_error(self):
        pytest.skip("pending implementation: spec-003")

    def test_tool_failure_returns_structured_error_not_raw_exception(self):
        pytest.skip("pending implementation: spec-003")

    def test_agent_loop_stops_at_max_tool_iterations(self):
        pytest.skip("pending implementation: spec-003")

    def test_write_tool_is_idempotent_on_retry(self):
        pytest.skip("pending implementation: spec-003")
