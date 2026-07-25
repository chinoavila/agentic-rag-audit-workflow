import pytest


@pytest.mark.spec_010
class TestContratoErrorApi:
    """Spec-010: Contrato de Error Uniforme de API (.ai/specs/platform/spec-010-contrato-error-api.md)"""

    def test_errors_use_http_exception_not_200_with_error_flag(self):
        pytest.skip("pending implementation: spec-010")

    def test_error_body_matches_uniform_shape(self):
        pytest.skip("pending implementation: spec-010")

    def test_only_documented_status_codes_are_used(self):
        pytest.skip("pending implementation: spec-010")

    def test_pydantic_validation_errors_preserve_detail(self):
        pytest.skip("pending implementation: spec-010")
