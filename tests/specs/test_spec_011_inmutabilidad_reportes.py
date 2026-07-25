import pytest


@pytest.mark.spec_011
class TestInmutabilidadReportes:
    """Spec-011: Inmutabilidad de Reportes Generados (.ai/specs/audit/spec-011-inmutabilidad-reportes.md)"""

    def test_no_physical_delete_endpoint_exists_for_reports(self):
        pytest.skip("pending implementation: spec-011")

    def test_regenerating_report_supersedes_without_deleting_blob(self):
        pytest.skip("pending implementation: spec-011")

    def test_created_at_immutable_after_creation(self):
        pytest.skip("pending implementation: spec-011")

    def test_updated_at_changes_on_supersede(self):
        pytest.skip("pending implementation: spec-011")

    def test_full_version_history_of_report_is_retrievable(self):
        pytest.skip("pending implementation: spec-011")
