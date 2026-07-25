import pytest


@pytest.mark.spec_008
class TestUmbralRelevancia:
    """Spec-008: Umbral de Relevancia de Retrieval (.ai/specs/rag/spec-008-umbral-relevancia.md)"""

    def test_low_similarity_retrieval_declares_no_evidence(self):
        pytest.skip("pending implementation: spec-008")

    def test_high_similarity_retrieval_generates_grounded_answer(self):
        pytest.skip("pending implementation: spec-008")

    def test_lowering_similarity_threshold_triggers_guardrail_warning(self):
        pytest.skip("pending implementation: spec-008")
