import pytest


@pytest.mark.spec_012
class TestGeneracionInformesPlantilla:
    """Spec-012: Contrato de Generación de Informes desde Plantilla (.ai/specs/audit/spec-012-generacion-informes-plantilla.md)"""

    def test_generate_report_rejects_invalid_input_schema(self):
        pytest.skip("pending implementation: spec-012")

    def test_llm_cannot_modify_template_structure_outside_placeholders(self):
        pytest.skip("pending implementation: spec-012")

    def test_narrative_sections_cite_source_findings(self):
        pytest.skip("pending implementation: spec-012")

    def test_rubric_failure_blocks_publication_with_structured_feedback(self):
        pytest.skip("pending implementation: spec-012")

    def test_report_requires_human_approval_before_persisted_as_published(self):
        pytest.skip("pending implementation: spec-012")
