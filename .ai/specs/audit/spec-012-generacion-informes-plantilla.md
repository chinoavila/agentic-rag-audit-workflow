# Spec: Contrato de Generación de Informes desde Plantilla (spec-012)

## Summary
La tool `generate_report` rellena una plantilla de informe suministrada por el usuario con
hallazgos recuperados vía RAG. El LLM solo completa placeholders de prosa explícitamente
definidos por la plantilla — nunca regenera el documento libremente — y el borrador debe
pasar rúbricas automáticas y la aprobación humana de spec-006 antes de publicarse.

## Acceptance Criteria

- [ ] La tool `generate_report` declara `input_schema` (`template_id`, `audit_case_id`,
      secciones a completar) y valida el input contra él antes de ejecutar (spec-003).
- [ ] El LLM completa únicamente los placeholders de prosa definidos en la plantilla
      (p. ej. `{{narrativa_seccion}}`); no puede alterar estructura, encabezados ni tablas
      fijas de la plantilla.
- [ ] Cada afirmación en la narrativa generada cita el hallazgo/evidencia de origen, con el
      mismo contrato de grounding de spec-001.
- [ ] Antes de publicar, el borrador pasa rúbricas automáticas verificables: completitud
      (todas las secciones obligatorias presentes), citas válidas, conformidad de formato
      contra la plantilla.
- [ ] Si alguna rúbrica falla, el informe no se publica y se retorna feedback estructurado
      (qué rúbrica falló y por qué), reutilizable para un reintento.
- [ ] Ningún informe se persiste con estado "publicado" sin pasar el paso de aprobación
      humana de spec-006.

## Test Cases

- `test_generate_report_rejects_invalid_input_schema`
- `test_llm_cannot_modify_template_structure_outside_placeholders`
- `test_narrative_sections_cite_source_findings`
- `test_rubric_failure_blocks_publication_with_structured_feedback`
- `test_report_requires_human_approval_before_persisted_as_published`

## Implementation Notes

- Affected files: tool `generate_report` en `audit-tools`, motor de rubric-checking, paso de
  aprobación en `chainlit-ui`.
- Dependencies: spec-001 (citas), spec-003 (contrato de tool), spec-006 (human-in-the-loop),
  spec-011 (persistencia inmutable del resultado).
- Quick Rules referenced: `agentic-tool-use` (reglas 1, 2, 5), `audit-domain-rules` (regla 2).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [agentic-tool-use/SKILL.md](../../skills/agentic-tool-use/SKILL.md)
- [audit-domain-rules/SKILL.md](../../skills/audit-domain-rules/SKILL.md)

### Specs Relacionadas
- [spec-001-grounding-citacion.md](../rag/spec-001-grounding-citacion.md)
- [spec-006-human-in-the-loop.md](spec-006-human-in-the-loop.md)
- [spec-011-inmutabilidad-reportes.md](spec-011-inmutabilidad-reportes.md)

### Archivo de Test
- `tests/specs/test_spec_012_generacion_informes_plantilla.py`
