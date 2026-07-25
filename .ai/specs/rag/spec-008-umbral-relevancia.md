# Spec: Umbral de Relevancia de Retrieval (spec-008)

## Summary
Cuando el retrieval no encuentra chunks suficientemente relevantes, el agente debe declarar
explícitamente que no hay evidencia suficiente en vez de generar una respuesta plausible
pero sin sustento (alucinación).

## Acceptance Criteria

- [ ] Existe un `SIMILARITY_THRESHOLD` configurado y documentado.
- [ ] Si el score del mejor resultado está por debajo del umbral, la respuesta declara
      explícitamente falta de evidencia (no genera una afirmación de auditoría igual).
- [ ] El umbral es configurable pero cualquier cambio a un valor que lo baje disparo una
      advertencia del guardrail (`pre-tool-guard`) para revisión humana.
- [ ] `top_k` tiene un límite superior razonable (guardrail advierte con valores ≥30).
- [ ] Existe al menos un test con una query fuera de dominio (sin chunks relevantes en la
      colección) que confirma la respuesta "sin evidencia".

## Test Cases

- `test_low_similarity_retrieval_declares_no_evidence`
- `test_high_similarity_retrieval_generates_grounded_answer`
- `test_lowering_similarity_threshold_triggers_guardrail_warning`

## Implementation Notes

- Affected files: módulo de retrieval en `rag-engineer`, config compartida con
  `agentic-core`.
- Dependencies: skill `rag-retrieval` (regla 2), `.ai/guardrails/restricted-ops.json`
  (`blocked_soft_warning` sobre `similarity_threshold`/`top_k`).
- Quick Rules referenced: `rag-retrieval` (reglas 2, 3).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [rag-retrieval/SKILL.md](../../skills/rag-retrieval/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_008_umbral_relevancia.py`
