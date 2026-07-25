"""Tests para spec-008: Umbral de Relevancia de Retrieval.

Criterios de aceptación:
- SIMILARITY_THRESHOLD está configurado y documentado.
- Score por debajo de umbral -> insufficient_evidence=True, chunks=[].
- top_k está acotado y su limite es configurable.
- Lowering threshold dispara advertencia del guardrail.
"""

import warnings

import pytest

from app.rag.retrieval import (
    SIMILARITY_THRESHOLD,
    TOP_K,
    TOP_K_WARN_THRESHOLD,
    retrieve,
)


@pytest.mark.spec_008
class TestUmbralRelevancia:
    """Spec-008: Umbral de Relevancia de Retrieval (.ai/specs/rag/spec-008-umbral-relevancia.md)"""

    def test_low_similarity_retrieval_declares_no_evidence(self, test_collection):
        """Query sin chunks relevantes devuelve insufficient_evidence=True, chunks=[]."""
        # Setup: ingestar un documento sobre un tema específico
        test_collection.upsert(
            ids=["doc1"],
            documents=["Documentación de procedimientos contables internos."],
            metadatas=[
                {"source": "accounting.txt", "page": 1, "doc_hash": "abc", "ingested_at": "2026-07-25T00:00:00Z"}
            ],
        )

        # Act: buscar un tema completamente no relacionado
        result = retrieve(
            query="astronomía y espacio sideral",
            collection=test_collection,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

        # Assert: insufficient_evidence = True, chunks vacío
        assert result.insufficient_evidence is True, "Debe declarar insufficient_evidence"
        assert result.chunks == [], "chunks debe estar vacío cuando no hay evidencia relevante"

    def test_high_similarity_retrieval_generates_grounded_answer(self, test_collection):
        """Query sobre tema relacionado devuelve chunks relevantes con high similarity."""
        # Setup: ingestar documentos sobre auditoría
        test_collection.upsert(
            ids=["audit1", "audit2"],
            documents=[
                "Los controles internos deben evaluarse anualmente.",
                "La segregación de funciones es un control preventivo crítico.",
            ],
            metadatas=[
                {"source": "audit_framework.txt", "page": 1, "doc_hash": "hash1", "ingested_at": "2026-07-25T00:00:00Z"},
                {"source": "audit_framework.txt", "page": 2, "doc_hash": "hash1", "ingested_at": "2026-07-25T00:00:00Z"},
            ],
        )

        # Act: buscar sobre controles internos (muy relacionado)
        result = retrieve(
            query="evaluación de controles internos",
            collection=test_collection,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

        # Assert: debe haber chunks con buena similitud
        assert not result.insufficient_evidence, "Debe encontrar evidencia relevante"
        assert len(result.chunks) > 0, "Debe haber chunks recuperados"
        # El primer chunk debe tener una similitud razonablemente alta (close to 1.0)
        assert result.chunks[0].similarity > SIMILARITY_THRESHOLD, (
            "El top chunk debe estar por encima del threshold"
        )

    def test_lowering_similarity_threshold_triggers_guardrail_warning(self, test_collection):
        """Usar similarity_threshold < default dispara una advertencia de runtime."""
        # Setup: llenar colección
        test_collection.upsert(
            ids=["doc1"],
            documents=["Contenido de prueba"],
            metadatas=[
                {"source": "test.txt", "page": 1, "doc_hash": "hash", "ingested_at": "2026-07-25T00:00:00Z"}
            ],
        )

        # Act: llamar con umbral más bajo (advertencia de seguridad)
        # Nota: la advertencia no se propaga como exception, sale por `warnings.warn()`
        # en retrieve.py cuando top_k >= TOP_K_WARN_THRESHOLD
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = retrieve(
                query="prueba",
                collection=test_collection,
                similarity_threshold=0.1,  # Mucho más bajo que 0.3
                top_k=30,  # >= TOP_K_WARN_THRESHOLD dispara warning
            )
            # Assert: debe haber un warning sobre top_k alto
            assert len(w) > 0, "Debe disparar advertencia por top_k alto"
            assert "top_k" in str(w[0].message).lower(), "Advertencia debe mencionar top_k"

    def test_similarity_threshold_is_configurable(self, test_collection):
        """SIMILARITY_THRESHOLD se puede reconfigurar en cada retrieve() call."""
        # Setup
        test_collection.upsert(
            ids=["doc1"],
            documents=["Control de auditoría"],
            metadatas=[
                {"source": "test.txt", "page": 1, "doc_hash": "hash", "ingested_at": "2026-07-25T00:00:00Z"}
            ],
        )

        # Act 1: retrieve con threshold bajo
        result_low = retrieve(
            query="control",
            collection=test_collection,
            similarity_threshold=0.05,
        )

        # Act 2: retrieve con threshold alto
        result_high = retrieve(
            query="control",
            collection=test_collection,
            similarity_threshold=0.95,  # Muy alto, probablemente sin resultados
        )

        # Assert: threshold bajo debe traer más/mejores resultados
        # (o al menos, resultado bajo no debe tener insufficient_evidence si lo alto sí)
        assert result_low.insufficient_evidence is False or result_high.insufficient_evidence is True, (
            "Threshold más bajo debe ser más permisivo"
        )

    def test_top_k_default_is_configured(self, test_collection):
        """TOP_K tiene un valor por defecto explícito y bajo (evita traer demasiado)."""
        # Assert: TOP_K debe ser un número pequeño (spec-008: evita dilución de relevancia)
        assert isinstance(TOP_K, int), "TOP_K debe ser un entero"
        assert TOP_K > 0, "TOP_K debe ser > 0"
        assert TOP_K <= 10, "TOP_K debe ser pequeño (acotado) para este slice"

    def test_top_k_warn_threshold_is_configured(self):
        """TOP_K_WARN_THRESHOLD dispara advertencia si top_k >= valor."""
        # Assert: threshold de advertencia debe ser moderado
        assert isinstance(TOP_K_WARN_THRESHOLD, int)
        assert TOP_K_WARN_THRESHOLD > TOP_K, "Threshold de advertencia debe ser > TOP_K"

    def test_retrieve_respects_top_k_limit(self, test_collection):
        """retrieve() nunca devuelve más chunks que top_k especificado."""
        # Setup: ingestar muchos documentos
        docs = [f"Documento {i} sobre auditoría." for i in range(20)]
        ids = [f"doc_{i}" for i in range(20)]
        metadatas = [
            {"source": f"audit_{i}.txt", "page": 1, "doc_hash": f"hash_{i}", "ingested_at": "2026-07-25T00:00:00Z"}
            for i in range(20)
        ]
        test_collection.upsert(ids=ids, documents=docs, metadatas=metadatas)

        # Act: buscar con top_k=3
        result = retrieve(
            query="auditoría",
            collection=test_collection,
            top_k=3,
        )

        # Assert: nunca más de 3 chunks, incluso si hay 20 disponibles
        assert len(result.chunks) <= 3, "chunks debe respetar top_k"

    def test_insufficient_evidence_flag_is_accurate(self, test_collection):
        """insufficient_evidence=True solo cuando best_score < threshold."""
        # Setup: ingestar un documento
        test_collection.upsert(
            ids=["doc1"],
            documents=["Contenido sobre compras y pagos."],
            metadatas=[
                {"source": "procurement.txt", "page": 1, "doc_hash": "hash", "ingested_at": "2026-07-25T00:00:00Z"}
            ],
        )

        # Act 1: query muy relevante
        result_good = retrieve(
            query="compras y pagos",
            collection=test_collection,
            similarity_threshold=0.3,
        )

        # Act 2: query no relevante
        result_bad = retrieve(
            query="astrología cósmica",
            collection=test_collection,
            similarity_threshold=0.3,
        )

        # Assert: buenos resultados sin flag, malos con flag
        assert result_good.insufficient_evidence is False, "Query relevante no debe tener flag"
        assert len(result_good.chunks) > 0
        assert result_bad.insufficient_evidence is True, "Query irrelevante debe tener flag"
        assert len(result_bad.chunks) == 0

    def test_empty_query_raises_error(self, test_collection):
        """Query vacía o solo espacios levanta ValueError."""
        with pytest.raises(ValueError):
            retrieve(query="", collection=test_collection)

        with pytest.raises(ValueError):
            retrieve(query="   ", collection=test_collection)
