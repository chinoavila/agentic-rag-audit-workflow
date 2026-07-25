# Spec: Exposición Dinámica de Tools vía Retrieval (spec-013)

## Summary
Cuando el catálogo de `audit-tools` crece, el agente no debe recibir las N tools completas
en cada turno. En su lugar, recupera solo el subconjunto cuya documentación indexada supera
el umbral de relevancia frente a la intención del turno — mismo mecanismo y mismo umbral que
ya rige el retrieval documental (spec-008).

## Acceptance Criteria

- [ ] La documentación de cada tool (nombre, descripción, ejemplos de uso) está indexada en
      un vector store separado del de documentos de auditoría.
- [ ] Antes de cada turno con tool-calling, se recupera el subconjunto de tools cuyo score de
      relevancia frente al mensaje del usuario supera `SIMILARITY_THRESHOLD` (mismo umbral
      configurado en spec-008, o uno propio igual de explícito y documentado).
- [ ] Existe un tope razonable de tools expuestas por turno (guardrail advierte si se excede,
      análogo al límite de `top_k` en spec-008).
- [ ] Si ninguna tool indexada supera el umbral, el agente responde sin tool-calling en vez de
      forzar una tool irrelevante.
- [ ] La documentación recuperada de la tool se pasa como declaración de tool a la API
      (parámetro `tools`), nunca reescrita en el system prompt (regla 4 de
      `agentic-tool-use`).
- [ ] Agregar una tool nueva al índice la hace elegible sin cambios de código en el loop
      agéntico.

## Test Cases

- `test_tool_docs_indexed_in_separate_vector_store`
- `test_only_tools_above_threshold_are_exposed_to_llm`
- `test_no_relevant_tool_falls_back_to_no_tool_call`
- `test_tool_declaration_passed_via_tools_param_not_system_prompt`
- `test_new_indexed_tool_becomes_eligible_without_code_change`

## Implementation Notes

- Affected files: pipeline de ingesta de tool-docs en `rag-engineer`, loop de selección de
  tools en `agentic-core`.
- Dependencies: spec-008 (mismo umbral/mecanismo de relevancia), skill `agentic-tool-use`
  (regla 4).
- Quick Rules referenced: `rag-retrieval` (reglas 2, 3), `agentic-tool-use` (regla 4).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [rag-retrieval/SKILL.md](../../skills/rag-retrieval/SKILL.md)
- [agentic-tool-use/SKILL.md](../../skills/agentic-tool-use/SKILL.md)

### Specs Relacionadas
- [spec-008-umbral-relevancia.md](spec-008-umbral-relevancia.md) — mismo umbral, aplicado a
  documentación de tools en vez de documentos de auditoría.

### Archivo de Test
- `tests/specs/test_spec_013_exposicion_dinamica_tools_retrieval.py`
