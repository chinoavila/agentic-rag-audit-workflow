# Spec: RAG Grounding & Citación Obligatoria (spec-001)

## Summary
Toda respuesta del agente que se apoye en contexto recuperado (RAG) debe poder citar
explícitamente el/los chunk(s) fuente (documento + página) que la sustentan. Ninguna
afirmación de auditoría se presenta como hecho sin evidencia citable.

## Acceptance Criteria

- [ ] Toda respuesta que use contexto RAG incluye un campo `citations` no vacío con
      `{source, page, chunk_id}` por cada afirmación relevante.
- [ ] Si no hay chunks por encima del umbral de relevancia (ver spec-008), la respuesta no
      contiene afirmaciones sin cita — declara explícitamente falta de evidencia.
- [ ] Las citas referencian chunks que realmente fueron parte del contexto pasado al LLM en
      ese turno (no citas inventadas/alucinadas).
- [ ] Un hallazgo de auditoría (`audit-tools`) sin `evidence` no puede crearse (ver spec
      relacionada spec-004/audit-domain-rules).
- [ ] El formato de cita es consistente en toda la app (mismo shape en API y en el chat).

## Test Cases

- `test_response_with_rag_context_includes_citations`
- `test_response_without_relevant_context_declares_no_evidence`
- `test_citations_reference_chunks_actually_in_context`
- `test_finding_creation_without_evidence_is_rejected`

## Implementation Notes

- Affected files: módulo de ensamblado de contexto en `agentic-core`, módulo de retrieval en
  `rag-engineer`, modelo de `Finding` en `audit-tools`/`backend-api`.
- Dependencies: spec-008 (umbral de relevancia), skill `rag-retrieval`, skill
  `audit-domain-rules`.
- Quick Rules referenced: `rag-retrieval` (regla 1), `audit-domain-rules` (regla 2).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [rag-retrieval/SKILL.md](../../skills/rag-retrieval/SKILL.md)
- [audit-domain-rules/SKILL.md](../../skills/audit-domain-rules/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_001_grounding_citacion.py`
