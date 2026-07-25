import pytest


@pytest.mark.spec_004
class TestInmutabilidadAuditTrail:
    """Spec-004: Inmutabilidad del Audit Trail (.ai/specs/audit/spec-004-inmutabilidad-audit-trail.md)"""

    def test_no_physical_delete_endpoint_exists_for_findings(self):
        pytest.skip("pending implementation: spec-004")

    def test_supersede_preserves_original_record(self):
        pytest.skip("pending implementation: spec-004")

    def test_created_at_immutable_after_creation(self):
        pytest.skip("pending implementation: spec-004")

    def test_updated_at_changes_on_supersede(self):
        pytest.skip("pending implementation: spec-004")

    def test_full_history_of_finding_is_retrievable(self):
        pytest.skip("pending implementation: spec-004")
