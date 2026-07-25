"""Tests para spec-001: RAG Grounding & Citación Obligatoria.

Criterios de aceptación:
- Respuestas con contexto RAG incluyen citas (source+page).
- Sin contexto relevante: se declara insufficient_evidence en vez de alucinar.
- Las citas referencian chunks que realmente están en el contexto.
- Un Finding sin evidence es rechazado (422).
"""

import pytest
from pydantic import ValidationError

from app.rag.retrieval import RetrievedChunk, RetrievalResult, retrieve
from app.schemas.finding import Citation, FindingCreate


@pytest.mark.spec_001
class TestGroundingCitacion:
    """Spec-001: RAG Grounding & Citacion Obligatoria (.ai/specs/rag/spec-001-grounding-citacion.md)"""

    def test_response_with_rag_context_includes_citations(self, test_collection):
        """Respuesta con contexto RAG incluye citas (source+page) en cada chunk."""
        # Setup: ingesta un documento ficticio
        chunk_text_1 = "Los controles internos deben estar documentados."
        chunk_text_2 = "Cada transacción debe tener auditoría."
        test_collection.upsert(
            ids=["doc1_1", "doc1_2"],
            documents=[chunk_text_1, chunk_text_2],
            metadatas=[
                {"source": "audit_policy.txt", "page": 1, "doc_hash": "abc123", "ingested_at": "2026-07-25T00:00:00Z"},
                {"source": "audit_policy.txt", "page": 2, "doc_hash": "abc123", "ingested_at": "2026-07-25T00:00:00Z"},
            ],
        )

        # Act: búsqueda con retrieval
        result = retrieve("controles internos", collection=test_collection)

        # Assert: resultado tiene chunks, cada uno con source+page
        assert result.chunks, "Esperado chunks recuperados"
        for chunk in result.chunks:
            assert chunk.source == "audit_policy.txt", "source debe estar presente"
            assert chunk.page >= 1, "page debe ser un número válido"
            assert chunk.chunk_id, "chunk_id debe estar presente"
            assert chunk.similarity >= 0.0, "similarity debe estar disponible"

    def test_response_without_relevant_context_declares_no_evidence(self, test_collection):
        """Sin contexto relevante: insufficient_evidence=True, chunks=[], no alucinación."""
        # Setup: colección vacía
        # (test_collection está vacía por default)

        # Act: búsqueda con query no relacionada
        result = retrieve("tema completamente aleatorio sin relación", collection=test_collection)

        # Assert: insufficient_evidence=True, chunks vacío
        assert result.insufficient_evidence is True, "Debe declarar insufficient_evidence"
        assert result.chunks == [], "chunks debe estar vacío cuando no hay evidencia"

    def test_citations_reference_chunks_actually_in_context(self, test_collection):
        """Las citas referencian chunks que realmente están en el contexto recuperado."""
        # Setup: ingesta múltiples chunks
        docs = ["Control A: revisión de compras", "Control B: auditoría de nómina"]
        test_collection.upsert(
            ids=["ctrl_1", "ctrl_2"],
            documents=docs,
            metadatas=[
                {"source": "controls.txt", "page": 1, "doc_hash": "ctrl_hash", "ingested_at": "2026-07-25T00:00:00Z"},
                {"source": "controls.txt", "page": 2, "doc_hash": "ctrl_hash", "ingested_at": "2026-07-25T00:00:00Z"},
            ],
        )

        # Act: búsqueda
        result = retrieve("control compras", collection=test_collection)

        # Assert: cada chunk en result.chunks debe venir de los que metimos
        retrieved_ids = {chunk.chunk_id for chunk in result.chunks}
        assert retrieved_ids.issubset({"ctrl_1", "ctrl_2"}), "Los chunks recuperados deben ser de los que ingesta"

    def test_finding_creation_without_evidence_is_rejected(self):
        """Un Finding sin evidence (lista vacía) es rechazado con ValidationError."""
        # Act & Assert: Pydantic rechaza evidence vacío
        with pytest.raises(ValidationError) as exc_info:
            FindingCreate(
                case_id="case_001",
                title="Test Finding",
                description="Test description",
                severity="medium",
                evidence=[],  # EMPTY - spec-001 regla 2: evidence obligatoria
                risk_score=5.0,
            )

        # Verificar que el error es sobre evidence
        errors = exc_info.value.errors()
        assert any("evidence" in str(e) for e in errors), "Error debe mencionar evidence"

    def test_citations_with_valid_evidence_list(self):
        """Las citas (Citations) con formato válido se aceptan en FindingCreate."""
        # Act: crear un FindingCreate con evidence válida
        finding = FindingCreate(
            case_id="case_001",
            title="Valid Finding",
            description="Con citas",
            severity="high",
            evidence=[
                Citation(source="doc1.txt", page=1),
                Citation(source="doc2.txt", page=None),  # page es opcional
            ],
            risk_score=7.5,
        )

        # Assert: el modelo se crea exitosamente
        assert len(finding.evidence) == 2
        assert finding.evidence[0].source == "doc1.txt"
        assert finding.evidence[0].page == 1
        assert finding.evidence[1].source == "doc2.txt"
        assert finding.evidence[1].page is None
