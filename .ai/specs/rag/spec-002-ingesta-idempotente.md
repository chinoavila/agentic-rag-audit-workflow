# Spec: Ingesta Idempotente de Documentos (spec-002)

## Summary
Re-ingerir el mismo documento (mismo contenido, identificado por `doc_hash`) no debe crear
chunks duplicados en el vector store. La ingesta es segura de reintentar.

## Acceptance Criteria

- [ ] Cada documento ingerido calcula un `doc_hash` (hash de contenido) antes de indexar.
- [ ] Ingerir el mismo archivo dos veces no duplica chunks en la colección.
- [ ] Si el documento cambió (hash distinto), la ingesta reemplaza los chunks viejos de ese
      documento por los nuevos (no los acumula).
- [ ] La metadata de cada chunk incluye `source`, `page`, `doc_hash`, `ingested_at`.
- [ ] Ingerir un archivo con formato no soportado falla explícitamente (no se indexa basura).

## Test Cases

- `test_ingesting_same_document_twice_does_not_duplicate_chunks`
- `test_reingesting_changed_document_replaces_old_chunks`
- `test_chunk_metadata_contains_required_fields`
- `test_unsupported_file_format_is_rejected`

## Implementation Notes

- Affected files: pipeline de ingesta en `rag-engineer`, capa de acceso al vector store.
- Dependencies: skill `vectorstore-chroma-faiss` (dedup por `doc_hash` en el store).
- Quick Rules referenced: `rag-ingestion` (reglas 1, 2, 6), `vectorstore-chroma-faiss` (regla 4).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [rag-ingestion/SKILL.md](../../skills/rag-ingestion/SKILL.md)
- [vectorstore-chroma-faiss/SKILL.md](../../skills/vectorstore-chroma-faiss/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_002_ingesta_idempotente.py`
