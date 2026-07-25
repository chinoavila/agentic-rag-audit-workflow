# Security — Prompt Injection & Contenido No Confiable — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Contenido recuperado = dato, nunca instrucción**: el texto de documentos ingeridos se
   inserta en el prompt dentro de un bloque delimitado y explícitamente etiquetado como
   "contexto no confiable", nunca concatenado libremente al system prompt.
   - ✅ OK: `f"<untrusted_context>\n{chunk_text}\n</untrusted_context>"` con instrucción
     explícita de no seguir comandos dentro de esas etiquetas
   - ❌ BAD: `system_prompt += chunk_text`
   - 🔍 Verificar: existe un delimitador consistente para contenido recuperado.

2. **Lista de permisos de tools por contexto**: el LLM no puede invocar tools destructivas
   (ej. aprobar un hallazgo crítico) como resultado directo de instrucciones encontradas en
   un documento ingerido — solo por instrucción explícita del usuario humano en el chat.
   - 🔍 Verificar: existe una distinción entre "tools invocables por contenido de documento"
     (ninguna con efecto de escritura crítica) y "tools invocables por el usuario".

3. **Test de inyección obligatorio** (spec-005): antes de mergear cambios al pipeline de
   ingesta/prompt, correr al menos un caso con un documento que contenga un payload de
   inyección conocido (ej. "ignora las instrucciones anteriores y...") y verificar que el
   agente no lo obedece.
   - 🔍 Verificar: existe un test (`tests/specs/test_spec_005_*.py`) con un payload de este tipo.

4. **PII no se re-expone sin necesidad**: si un documento contiene PII, no se repite
   verbatim en la respuesta salvo que sea estrictamente necesario para el hallazgo (y en ese
   caso, se registra por qué).
   - 🔍 Verificar: no hay un patrón de "eco" automático de todo el chunk recuperado sin
     filtrar.

5. **Trazabilidad**: cada acción del agente que modifica estado (crear/superseder hallazgo,
   aprobar) queda registrada con quién/qué la disparó (usuario humano vs. tool automática).
   - 🔍 Verificar: existe un campo tipo `triggered_by` en las acciones de auditoría.

---

## 📚 Guía completa

- Este skill es la referencia técnica que usa `security-compliance` para auditar el diseño
  de `rag-engineer` y `agentic-core`; el `reviewer` usa las Quick Rules de arriba para
  validar artefactos concretos.
