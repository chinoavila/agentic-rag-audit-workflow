# Agentic Tool Use — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Schema de tool explícito y validado**: cada tool declara su input/output con JSON
   Schema (o Pydantic), nunca recibe un string libre sin parsear.
   - ✅ OK: `{"name": "create_finding", "input_schema": {"type": "object", "properties": {...}, "required": [...]}}`
   - ❌ BAD: una tool que recibe `raw_text: str` y hace su propio parsing ad-hoc
   - 🔍 Verificar: toda tool expuesta al LLM tiene `input_schema` definido.

2. **Errores estructurados, nunca excepciones crudas al LLM** (spec-003): una tool que falla
   retorna `{"error": "...", "code": "..."}`, no deja que la excepción se propague sin control.
   - ✅ OK: `try: ... except ValueError as e: return {"error": str(e), "code": "invalid_input"}`
   - ❌ BAD: dejar que un stack trace completo se inserte como resultado de la tool
   - 🔍 Verificar: cada tool tiene manejo de errores que retorna un objeto estructurado.

3. **Límite de iteraciones del loop** (`max_tool_iterations`): configurado explícitamente y
   bajo (guardrail: valores ≥20 disparan advertencia).
   - 🔍 Verificar: existe una constante `max_tool_iterations` y el loop la respeta.

4. **Contenido de tools = dato, nunca instrucción del sistema**: el resultado de una tool
   (incluido contexto RAG) se inserta como mensaje de rol `tool`/`user`, nunca se reescribe
   dentro del system prompt.
   - 🔍 Verificar: el resultado de la tool entra al historial con el rol correcto, no
     concatenado al system prompt.

5. **Salida estructurada para hallazgos de auditoría**: `audit-tools` siempre retorna JSON
   tipado (severidad, evidencia, cita), nunca prosa libre que luego hay que re-parsear.
   - 🔍 Verificar: el output de tools de auditoría es JSON validable contra un schema.

6. **Idempotencia de tools con efectos secundarios**: crear un hallazgo dos veces con el
   mismo input no duplica el registro (usar una clave de idempotencia).
   - 🔍 Verificar: existe alguna forma de detectar/evitar la duplicación en tools de escritura.

---

## 📚 Guía completa

- El loop agéntico vive en `agentic-core`; las tools de dominio (auditoría) viven en
  `audit-tools` — no mezclar orquestación con lógica de negocio en el mismo módulo.
- Ver spec-003 para el contrato completo de invocación segura.
