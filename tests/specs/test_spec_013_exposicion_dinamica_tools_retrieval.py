import pytest


@pytest.mark.spec_013
class TestExposicionDinamicaToolsRetrieval:
    """Spec-013: Exposición Dinámica de Tools vía Retrieval (.ai/specs/rag/spec-013-exposicion-dinamica-tools-retrieval.md)"""

    def test_tool_docs_indexed_in_separate_vector_store(self):
        pytest.skip("pending implementation: spec-013")

    def test_only_tools_above_threshold_are_exposed_to_llm(self):
        pytest.skip("pending implementation: spec-013")

    def test_no_relevant_tool_falls_back_to_no_tool_call(self):
        pytest.skip("pending implementation: spec-013")

    def test_tool_declaration_passed_via_tools_param_not_system_prompt(self):
        pytest.skip("pending implementation: spec-013")

    def test_new_indexed_tool_becomes_eligible_without_code_change(self):
        pytest.skip("pending implementation: spec-013")
