# Spec: Invocación Segura de Tools de Auditoría (spec-003)

## Summary
Las herramientas (`tools`) que el LLM puede invocar deben validar sus inputs, manejar
errores de forma estructurada y respetar un límite de iteraciones — nunca propagar
excepciones crudas ni entrar en loops sin control.

## Acceptance Criteria

- [ ] Toda tool expuesta al LLM declara `input_schema` y valida el input contra él antes de
      ejecutar lógica de negocio.
- [ ] Una tool que falla retorna `{"error": str, "code": str}` estructurado, nunca deja
      propagar un stack trace al contexto del LLM.
- [ ] El loop agéntico respeta `max_tool_iterations` (configurado y bajo); al alcanzarlo,
      corta con un mensaje explícito en vez de seguir iterando indefinidamente.
- [ ] Tools con efectos secundarios de escritura (crear/superseder hallazgo) son
      idempotentes ante reintentos con el mismo input.
- [ ] Existe un test que fuerza un input inválido y verifica el error estructurado.

## Test Cases

- `test_tool_rejects_invalid_input_with_structured_error`
- `test_tool_failure_returns_structured_error_not_raw_exception`
- `test_agent_loop_stops_at_max_tool_iterations`
- `test_write_tool_is_idempotent_on_retry`

## Implementation Notes

- Affected files: definición de tools en `agentic-core`/`audit-tools`, loop principal del
  agente.
- Dependencies: skill `agentic-tool-use`.
- Quick Rules referenced: `agentic-tool-use` (todas).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [agentic-tool-use/SKILL.md](../../skills/agentic-tool-use/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_003_invocacion_segura_tools.py`
