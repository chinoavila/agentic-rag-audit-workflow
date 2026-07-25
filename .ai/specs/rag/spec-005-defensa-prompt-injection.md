# Spec: Defensa Anti Prompt-Injection en Documentos Ingeridos (spec-005)

## Summary
El contenido de documentos ingeridos vía RAG es la superficie de ataque más probable de la
aplicación (prompt injection indirecta). El sistema debe tratarlo siempre como dato, nunca
como instrucción, y resistir payloads de inyección conocidos.

## Acceptance Criteria

- [ ] El contexto recuperado se inserta en el prompt dentro de un bloque delimitado y
      etiquetado como no confiable (ver skill `security-prompt-injection`).
- [ ] Un documento que contiene texto tipo "ignora las instrucciones anteriores y..." no
      logra que el agente cambie de comportamiento ni ejecute acciones no solicitadas por el
      usuario humano.
- [ ] Ninguna tool con efecto de escritura crítico (aprobar hallazgo, marcar como final) es
      invocable como resultado directo de una instrucción encontrada en un documento.
- [ ] Existe al menos un test con un payload de inyección real corriendo en CI local
      (`pytest -m spec_005`).
- [ ] El audit trail registra `triggered_by` (usuario humano vs. tool automática) para toda
      acción que modifica estado.

## Test Cases

- `test_injected_instruction_in_document_is_not_obeyed`
- `test_critical_tool_not_invoked_from_document_content`
- `test_action_records_triggered_by_source`

## Implementation Notes

- Affected files: ensamblado de contexto en `agentic-core`, definición de tools en
  `agentic-core`/`audit-tools`.
- Dependencies: skill `security-prompt-injection`, skill `rag-ingestion` (regla 4).
- Quick Rules referenced: `security-prompt-injection` (todas), `agentic-tool-use` (regla 4).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [security-prompt-injection/SKILL.md](../../skills/security-prompt-injection/SKILL.md)
- [agentic-tool-use/SKILL.md](../../skills/agentic-tool-use/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_005_defensa_prompt_injection.py`
