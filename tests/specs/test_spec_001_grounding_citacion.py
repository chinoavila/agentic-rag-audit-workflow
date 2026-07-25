import pytest


@pytest.mark.spec_001
class TestGroundingCitacion:
    """Spec-001: RAG Grounding & Citacion Obligatoria (.ai/specs/rag/spec-001-grounding-citacion.md)"""

    def test_response_with_rag_context_includes_citations(self):
        pytest.skip("pending implementation: spec-001")

    def test_response_without_relevant_context_declares_no_evidence(self):
        pytest.skip("pending implementation: spec-001")

    def test_citations_reference_chunks_actually_in_context(self):
        pytest.skip("pending implementation: spec-001")

    def test_finding_creation_without_evidence_is_rejected(self):
        pytest.skip("pending implementation: spec-001")
