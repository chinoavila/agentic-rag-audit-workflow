# Spec: Exposición Dinámica de Tools vía Retrieval (spec-013)

## Summary
Cuando el catálogo de `audit-tools` crece, el agente no debe recibir las N tools completas
en cada turno. En su lugar, recupera solo el subconjunto cuya documentación indexada supera
el umbral de relevancia frente a la intención del turno — mismo mecanismo y mismo umbral que
ya rige el retrieval documental (spec-008). Antes de llegar a ese umbral, el subconjunto
candidato pasa por un filtro estructural de elegibilidad basado en `ToolCatalogEntry.installed`
(catálogo global) y `ProjectTool.enabled` (override por proyecto, `case_id`): el retrieval
semántico nunca decide por sí solo si una tool puede exponerse, solo cuál de las ya elegibles
es relevante para el turno. Esto cierra el gap documentado en `docs/sdd-status.md` ("Sin
allowlist de tools según contexto"); el diseño fue corregido y aprobado en
`docs/plans/plan-tool-execution-permission-modes.md` (sección 3).

El modelo de elegibilidad es **default-on con override**: si `ToolCatalogEntry.installed=true`,
la tool está disponible en todos los proyectos por defecto — la ausencia de fila `ProjectTool`
para un `(case_id, tool_key)` dado NO significa "no disponible". Una fila
`ProjectTool.enabled=false` es la única forma de excluirla puntualmente para un proyecto. El
catálogo global tiene precedencia absoluta: `ToolCatalogEntry.installed=false` excluye la tool
de todos los proyectos sin excepción, incluso si existiera una fila `ProjectTool.enabled=true`.

## Acceptance Criteria

- [ ] Una tool es elegible para el índice de retrieval semántico de un turno si y solo si
      `ToolCatalogEntry.installed=true` **AND** (no existe fila `ProjectTool` para
      `(case_id, tool_key)` **OR** `ProjectTool.enabled=true`).
- [ ] `ProjectTool.enabled=false` es la única forma de excluir puntualmente, para un `case_id`,
      una tool instalada globalmente.
- [ ] `ToolCatalogEntry.installed=false` excluye la tool de todos los proyectos sin excepción,
      incluso si existiera `ProjectTool.enabled=true` para algún `case_id` (catálogo global
      tiene precedencia).
- [ ] Solo dentro del subconjunto elegible resultante se aplica `SIMILARITY_THRESHOLD`
      (spec-008, sin cambios de mecanismo).
- [ ] Existe un tope razonable de tools expuestas por turno (guardrail advierte si se excede,
      análogo a `top_k`).
- [ ] Si ninguna tool elegible supera el umbral, el agente responde sin tool-calling.
- [ ] La documentación recuperada se pasa vía parámetro `tools` de la API, nunca reescrita en
      el system prompt (regla 4 de `agentic-tool-use`).
- [ ] El predicado de elegibilidad vive en una única implementación compartida, consumida tanto
      por el índice de retrieval como por el endpoint `GET /api/audit-cases/{case_id}/tools` —
      nunca reimplementado en paralelo.

## Test Cases

- `test_tool_docs_indexed_in_separate_vector_store`
- `test_installed_tool_without_project_tool_row_is_eligible_by_default`
- `test_project_tool_enabled_false_excludes_installed_tool_for_that_case`
- `test_tool_catalog_installed_false_excludes_tool_even_with_project_tool_enabled_true`
- `test_only_eligible_tools_above_threshold_are_exposed_to_llm`
- `test_no_relevant_tool_falls_back_to_no_tool_call`
- `test_tool_declaration_passed_via_tools_param_not_system_prompt`

## Implementation Notes

- Affected files: pipeline de ingesta/índice de tool-docs en `rag-engineer`; helper compartido
  de elegibilidad y `GET /api/audit-cases/{case_id}/tools` en `backend-api`
  (`app/models/tool_catalog_entry.py`, `app/models/project_tool.py`); loop de selección de
  tools en `agentic-core`.
- Dependencies: spec-008 (mismo umbral/mecanismo de relevancia), skill `agentic-tool-use`
  (regla 4), `docs/plans/plan-tool-execution-permission-modes.md` (sección 3, diseño aprobado
  del filtro estructural).
- Quick Rules referenced: `rag-retrieval` (reglas 2, 3), `agentic-tool-use` (regla 4).
- El helper de elegibilidad es responsabilidad de `backend-api`; `rag-engineer` lo consume como
  paso previo al scoring de relevancia, sin reimplementar el predicado.

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [rag-retrieval/SKILL.md](../../skills/rag-retrieval/SKILL.md)
- [agentic-tool-use/SKILL.md](../../skills/agentic-tool-use/SKILL.md)

### Specs Relacionadas
- [spec-008-umbral-relevancia.md](spec-008-umbral-relevancia.md) — mismo umbral, aplicado a
  documentación de tools en vez de documentos de auditoría, y aplicado únicamente sobre el
  subconjunto ya elegible por el filtro estructural de esta spec.

### Archivo de Test
- `tests/specs/test_spec_013_exposicion_dinamica_tools_retrieval.py`
