# Vector Store (Chroma/FAISS) — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Persistencia en volumen dedicado**: la ruta `persist_directory`/índice FAISS vive en un
   volumen Docker montado, nunca en un directorio efímero del contenedor.
   - ✅ OK: `persist_directory="/data/chroma"` con `/data` montado como volumen en compose
   - ❌ BAD: `persist_directory="/tmp/chroma"` (se pierde al reiniciar el contenedor)
   - 🔍 Verificar: `docker-compose.yml` monta un volumen sobre la ruta de persistencia.

2. **Naming de colecciones explícito y versionado**: `{dominio}_{modelo_embedding}_v{n}`.
   - ✅ OK: `audit_docs_openai-text-embedding-3-small_v1`
   - ❌ BAD: `default` o `collection1`
   - 🔍 Verificar: el nombre de colección codifica dominio + modelo de embedding.

3. **Sin mezclar dimensiones de embeddings en una misma colección** (ver `rag-ingestion`
   regla 5).
   - 🔍 Verificar: un solo modelo de embeddings por colección, registrado en metadata.

4. **Dedup por `doc_hash` a nivel de vector store**, no solo a nivel de pipeline de ingesta
   (defensa en profundidad).
   - 🔍 Verificar: existe un índice/constraint sobre `doc_hash` en la metadata de la colección.

5. **Backup antes de reindexar completo**: cualquier operación de "borrar y reconstruir" la
   colección requiere snapshot previo del volumen.
   - 🔍 Verificar: existe un paso de backup documentado antes de un reindex completo.

---

## 📚 Guía completa

- `docker compose down -v` está bloqueado por guardrail (borra este volumen) — ver
  `.ai/guardrails/restricted-ops.json`.
- Ver spec-009 (entorno Docker reproducible) para el contrato de persistencia esperado.
