# RAG Ingestion — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Metadata obligatoria por chunk**: `source` (nombre/uri del doc), `page`, `doc_hash`,
   `ingested_at`.
   - ✅ OK: `Chunk(text=..., metadata={"source": "informe.pdf", "page": 4, "doc_hash": sha256, "ingested_at": ts})`
   - ❌ BAD: `Chunk(text=...)` sin metadata
   - 🔍 Verificar: todo chunk indexado tiene las 4 claves de metadata.

2. **Ingesta idempotente** (spec-002): re-ingerir el mismo documento (mismo `doc_hash`) no
   crea duplicados.
   - ✅ OK: `if doc_hash in indexed_hashes: skip_or_replace()`
   - ❌ BAD: insertar chunks nuevos cada vez sin chequear el hash del doc
   - 🔍 Verificar: existe un chequeo de `doc_hash` antes de indexar.

3. **Chunking con solapamiento controlado**: tamaño y overlap explícitos y documentados
   (no "lo que quede").
   - ✅ OK: `chunk_size=800, chunk_overlap=100` (constantes nombradas)
   - ❌ BAD: chunking ad-hoc por longitud de párrafo sin parámetros explícitos
   - 🔍 Verificar: existen constantes/config para `chunk_size`/`chunk_overlap`.

4. **Contenido ingerido es dato, no instrucción** (spec-005): nunca se ejecuta ni interpola
   directamente en el system prompt sin pasar por el flujo de retrieval + delimitadores.
   - 🔍 Verificar: no hay ningún paso que tome texto crudo de un documento y lo concatene al
     system prompt sin marcarlo como contenido de usuario/contexto.

5. **Consistencia de dimensión de embeddings**: un único modelo de embeddings por colección;
   cambiar de modelo requiere re-indexar toda la colección, no mezclar dimensiones.
   - 🔍 Verificar: la colección registra qué modelo de embeddings se usó.

6. **Rechazo de formatos no soportados**: la ingesta valida el tipo de archivo antes de
   procesar (no intenta parsear binarios como texto).
   - 🔍 Verificar: existe una validación explícita de extensión/mimetype.

---

## 📚 Guía completa

- Pipeline: `load → validate → chunk → embed → upsert(vectorstore)`, cada paso idempotente
  y logueado (para poder re-ejecutar sin duplicar).
- Ver `.ai/skills/vectorstore-chroma-faiss/SKILL.md` para las reglas de persistencia del
  índice.
