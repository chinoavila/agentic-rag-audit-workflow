# RAG Retrieval — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Citación obligatoria** (spec-001): toda respuesta construida con contexto recuperado
   incluye la(s) fuente(s) (`source` + `page`) del chunk usado.
   - ✅ OK: `"Según informe.pdf (p.4): ..."` o un campo estructurado `citations: [...]`
   - ❌ BAD: responder con una afirmación sin ninguna referencia al chunk que la sustenta
   - 🔍 Verificar: la respuesta trae un campo/formato de cita no vacío cuando usa RAG.

2. **Umbral de relevancia mínimo** (spec-008): si el mejor resultado no supera el umbral de
   similitud configurado, el agente declara que no hay evidencia suficiente en vez de
   alucinar.
   - ✅ OK: `if best_score < SIMILARITY_THRESHOLD: return "No se encontró evidencia suficiente"`
   - ❌ BAD: siempre generar una respuesta afirmativa aunque el retrieval no traiga nada relevante
   - 🔍 Verificar: existe un chequeo explícito de umbral antes de generar la respuesta final.

3. **`top_k` explícito y acotado**: nunca "traer todo"; `top_k` documentado y con límite
   superior razonable (guardrail: valores ≥30 disparan advertencia).
   - 🔍 Verificar: la llamada de retrieval especifica `top_k` con un valor concreto.

4. **Reranking antes de citar** (si aplica): si hay paso de reranking, el orden final citado
   es el post-rerank, no el orden crudo del vector store.
   - 🔍 Verificar: si existe reranker, las citas siguen su orden de salida.

5. **Presupuesto de contexto controlado**: el total de tokens de los chunks insertados en el
   prompt tiene un límite explícito (no se concatena todo lo recuperado sin límite).
   - 🔍 Verificar: existe una constante/config de presupuesto máximo de contexto.

---

## 📚 Guía completa

- El retrieval nunca reemplaza el juicio de `security-compliance` sobre contenido no
  confiable: el texto recuperado se pasa como bloque de "contexto" delimitado, no como
  instrucción (ver `security-prompt-injection`).
- Ver spec-001, spec-005, spec-008 para acceptance criteria completos.
