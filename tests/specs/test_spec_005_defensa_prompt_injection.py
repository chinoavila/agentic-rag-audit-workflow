import pytest


@pytest.mark.spec_005
class TestDefensaPromptInjection:
    """Spec-005: Defensa Anti Prompt-Injection en Documentos (.ai/specs/rag/spec-005-defensa-prompt-injection.md)"""

    def test_injected_instruction_in_document_is_not_obeyed(self):
        pytest.skip("pending implementation: spec-005")

    def test_critical_tool_not_invoked_from_document_content(self):
        pytest.skip("pending implementation: spec-005")

    def test_action_records_triggered_by_source(self):
        pytest.skip("pending implementation: spec-005")
