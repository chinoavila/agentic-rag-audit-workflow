# Spec: Inmutabilidad del Audit Trail (spec-004)

## Summary
Los hallazgos de auditoría y el audit trail son append-only: nunca se borran físicamente,
solo se marcan como `superseded_by` un registro nuevo. Esto preserva la trazabilidad
requerida en un contexto de auditoría.

## Acceptance Criteria

- [ ] Ningún modelo de hallazgo/audit trail expone una operación de `DELETE` física.
- [ ] "Eliminar" un hallazgo se implementa como `PATCH` que setea `superseded_by=<new_id>`,
      preservando el registro original con su `id`, `created_at` y contenido intactos.
- [ ] `created_at` nunca se modifica tras la creación; `updated_at` cambia en cada
      transición de estado (incluyendo el supersede).
- [ ] El endpoint API no expone ningún verbo/ruta que ejecute `db.delete(...)` sobre estas
      tablas (verificado por `pre-tool-guard` a nivel de comando y por `reviewer` a nivel de
      código).
- [ ] Recuperar el historial completo de un hallazgo (incluyendo versiones superseded) es
      posible vía API.

## Test Cases

- `test_no_physical_delete_endpoint_exists_for_findings`
- `test_supersede_preserves_original_record`
- `test_created_at_immutable_after_creation`
- `test_updated_at_changes_on_supersede`
- `test_full_history_of_finding_is_retrievable`

## Implementation Notes

- Affected files: modelo `Finding`/`AuditTrailEntry`, endpoints en `backend-api`, lógica en
  `audit-tools`.
- Dependencies: guardrail hard-block `DELETE FROM (audit_trail|audit_findings|findings)` en
  `.ai/guardrails/restricted-ops.json`.
- Quick Rules referenced: `audit-domain-rules` (reglas 3, 5), `fastapi` (regla 6).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [audit-domain-rules/SKILL.md](../../skills/audit-domain-rules/SKILL.md)
- [fastapi/SKILL.md](../../skills/fastapi/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_004_inmutabilidad_audit_trail.py`
