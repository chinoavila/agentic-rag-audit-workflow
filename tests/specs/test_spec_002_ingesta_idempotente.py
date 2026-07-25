"""Tests para spec-002: Ingesta Idempotente de Documentos.

Criterios de aceptación:
- Reingestar el mismo doc (mismo doc_hash) no duplica chunks.
- Reingestar un doc modificado reemplaza chunks viejos sin dejar huérfanos.
- Metadata obligatoria: source, page, doc_hash, ingested_at.
- Archivo con extensión no soportada es rechazado.
"""

import pytest

from app.rag.ingestion import (
    UnsupportedFormatError,
    compute_doc_hash,
    ingest_document,
    load_document,
    validate_supported_format,
)


@pytest.mark.spec_002
class TestIngestaIdempotente:
    """Spec-002: Ingesta Idempotente de Documentos (.ai/specs/rag/spec-002-ingesta-idempotente.md)"""

    def test_ingesting_same_document_twice_does_not_duplicate_chunks(self, test_doc_path, test_collection):
        """Reingestar el mismo doc (mismo hash) no duplica chunks (skipped_unchanged)."""
        # Setup: crear documento de test
        doc_file = test_doc_path / "test_doc.txt"
        doc_content = "Contenido de auditoría control interno."
        doc_file.write_text(doc_content)

        # Act: ingestar primera vez
        result1 = ingest_document(doc_file, collection=test_collection)
        chunks_after_first = test_collection.get(where={"source": "test_doc.txt"})
        count_after_first = len(chunks_after_first.get("ids") or [])

        # Act: ingestar segunda vez (mismo contenido = mismo hash)
        result2 = ingest_document(doc_file, collection=test_collection)
        chunks_after_second = test_collection.get(where={"source": "test_doc.txt"})
        count_after_second = len(chunks_after_second.get("ids") or [])

        # Assert: status del segundo debe ser "skipped_unchanged"
        assert result2.status == "skipped_unchanged", "Segundo intento debe ser skip"
        # Assert: cantidad de chunks no cambió
        assert count_after_first == count_after_second, "No debe duplicar chunks"

    def test_reingesting_changed_document_replaces_old_chunks(self, test_doc_path, test_collection):
        """Reingestar un doc modificado reemplaza chunks viejos (status='replaced')."""
        # Setup: crear documento
        doc_file = test_doc_path / "test_doc.txt"
        doc_file.write_text("Contenido original de auditoría.")

        # Act: ingestar versión 1
        result1 = ingest_document(doc_file, collection=test_collection)
        assert result1.status == "inserted"
        count_after_first = len(test_collection.get(where={"source": "test_doc.txt"}).get("ids") or [])

        # Modificar documento
        doc_file.write_text("Contenido completamente diferente después de revisión importante.")

        # Act: ingestar versión 2 (contenido cambiado, hash distinto)
        result2 = ingest_document(doc_file, collection=test_collection)

        # Assert: status debe ser "replaced"
        assert result2.status == "replaced", "Documento cambiado debe ser replaced"
        # Assert: chunks devueltos deben ser del nuevo documento
        assert result2.chunks_indexed > 0, "Debe haber nuevos chunks indexados"

    def test_chunk_metadata_contains_required_fields(self, test_doc_path, test_collection):
        """Cada chunk tiene metadata obligatoria: source, page, doc_hash, ingested_at."""
        # Setup: ingestar documento
        doc_file = test_doc_path / "metadata_test.txt"
        doc_file.write_text("Test content for metadata validation.")
        result = ingest_document(doc_file, collection=test_collection)

        # Act: recuperar chunks
        chunks = test_collection.get(where={"source": "metadata_test.txt"})
        metadatas = chunks.get("metadatas") or []

        # Assert: cada metadata debe tener los campos obligatorios
        assert metadatas, "Debe haber metadata para los chunks"
        for meta in metadatas:
            assert "source" in meta, "source es obligatorio"
            assert "page" in meta, "page es obligatorio"
            assert "doc_hash" in meta, "doc_hash es obligatorio"
            assert "ingested_at" in meta, "ingested_at es obligatorio"
            assert meta["source"] == "metadata_test.txt"
            assert isinstance(meta["page"], int) and meta["page"] >= 1
            assert len(meta["doc_hash"]) == 64  # SHA256 hex = 64 caracteres

    def test_unsupported_file_format_is_rejected(self, test_doc_path):
        """Archivo con extensión no soportada es rechazado explícitamente."""
        # Setup: crear archivo con extensión no soportada
        unsupported_file = test_doc_path / "data.xlsx"
        unsupported_file.write_text("fake excel content")

        # Act & Assert: load_document levanta UnsupportedFormatError
        with pytest.raises(UnsupportedFormatError) as exc_info:
            load_document(unsupported_file)

        # El mensaje debe mencionar la extensión no soportada
        assert ".xlsx" in str(exc_info.value) or "xlsx" in str(exc_info.value).lower()

    def test_validate_supported_format_rejects_unsupported(self, test_doc_path):
        """validate_supported_format rechaza extensiones no en SUPPORTED_EXTENSIONS."""
        # Setup: archivo .pdf
        pdf_file = test_doc_path / "doc.pdf"
        pdf_file.write_text("fake pdf")

        # Act & Assert
        with pytest.raises(UnsupportedFormatError):
            validate_supported_format(pdf_file)

    def test_compute_doc_hash_deterministic(self):
        """compute_doc_hash es determinista: mismo contenido = mismo hash."""
        content = "Contenido de auditoría con controles."
        hash1 = compute_doc_hash(content)
        hash2 = compute_doc_hash(content)

        assert hash1 == hash2, "Mismo contenido debe dar mismo hash"
        assert len(hash1) == 64, "SHA256 hex debe tener 64 caracteres"

    def test_compute_doc_hash_changes_with_content(self):
        """compute_doc_hash cambia cuando el contenido cambia."""
        hash1 = compute_doc_hash("contenido original")
        hash2 = compute_doc_hash("contenido modificado")

        assert hash1 != hash2, "Contenido distinto debe dar hash distinto"

    def test_supported_formats_only_txt_and_md(self, test_doc_path):
        """Solo .txt y .md son formatos soportados."""
        # .txt: debe aceptarse
        txt_file = test_doc_path / "test.txt"
        txt_file.write_text("content")
        validate_supported_format(txt_file)  # No debe lanzar

        # .md: debe aceptarse
        md_file = test_doc_path / "test.md"
        md_file.write_text("# Markdown")
        validate_supported_format(md_file)  # No debe lanzar

        # .docx: debe rechazarse
        docx_file = test_doc_path / "test.docx"
        docx_file.write_text("fake")
        with pytest.raises(UnsupportedFormatError):
            validate_supported_format(docx_file)
