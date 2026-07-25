import pytest


@pytest.mark.spec_006
class TestHumanInTheLoop:
    """Spec-006: Human-in-the-Loop para Hallazgos de Alto Riesgo (.ai/specs/audit/spec-006-human-in-the-loop.md)"""

    def test_high_severity_finding_starts_as_pending_review(self):
        pytest.skip("pending implementation: spec-006")

    def test_final_transition_requires_approved_by_and_approved_at(self):
        pytest.skip("pending implementation: spec-006")

    def test_low_severity_finding_can_reach_final_without_approval(self):
        pytest.skip("pending implementation: spec-006")

    def test_chainlit_exposes_approve_reject_action_for_pending_review(self):
        pytest.skip("pending implementation: spec-006")

    def test_rejected_finding_preserves_record(self):
        pytest.skip("pending implementation: spec-006")
