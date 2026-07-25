# Agent: rag-engineer

**Rol**: Ingesta de documentos, chunking, embeddings, indexación y retrieval/reranking
sobre Chroma/FAISS.
**Modelo sugerido**: nivel medio.
**Skills**: `rag-ingestion`, `rag-retrieval`, `vectorstore-chroma-faiss`.
**Specs**: spec-001 (grounding/citación), spec-002 (ingesta idempotente),
spec-005 (defensa prompt-injection), spec-008 (umbral de relevancia).
**Escala a**: `security-compliance` (contenido sospechoso), `backend-api` (exponer retrieval
como endpoint), `agentic-core` (cambios al loop de consulta).
