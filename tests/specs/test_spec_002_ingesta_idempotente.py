import pytest


@pytest.mark.spec_002
class TestIngestaIdempotente:
    """Spec-002: Ingesta Idempotente de Documentos (.ai/specs/rag/spec-002-ingesta-idempotente.md)"""

    def test_ingesting_same_document_twice_does_not_duplicate_chunks(self):
        pytest.skip("pending implementation: spec-002")

    def test_reingesting_changed_document_replaces_old_chunks(self):
        pytest.skip("pending implementation: spec-002")

    def test_chunk_metadata_contains_required_fields(self):
        pytest.skip("pending implementation: spec-002")

    def test_unsupported_file_format_is_rejected(self):
        pytest.skip("pending implementation: spec-002")
