# Spec: Inmutabilidad de Reportes Generados (spec-011)

## Summary
Los reportes generados por `audit-tools` (y el archivo asociado en blob storage) son
append-only, siguiendo el mismo contrato que ya rige `audit_trail`/`findings` (spec-004):
nunca se borran físicamente, solo se marcan como `superseded_by` un reporte nuevo.

## Acceptance Criteria

- [ ] Ningún modelo `Report` expone una operación de `DELETE` física.
- [ ] Regenerar/corregir un reporte se implementa creando una fila nueva que referencia la
      anterior; la fila anterior setea `superseded_by=<new_id>` y conserva su `id`,
      `created_at` y `blob_url` originales intactos.
- [ ] El archivo en blob storage de un reporte superseded no se borra físicamente; sigue
      siendo accesible vía su `report_id` histórico.
- [ ] `created_at` nunca se modifica tras la creación; `updated_at` cambia en cada
      transición de estado (incluyendo el supersede).
- [ ] El endpoint API no expone ningún verbo/ruta que ejecute `db.delete(...)` sobre `reports`
      ni borre el objeto en blob storage subyacente.
- [ ] Recuperar el historial completo de versiones de un reporte (incluyendo superseded) es
      posible vía API.

## Test Cases

- `test_no_physical_delete_endpoint_exists_for_reports`
- `test_regenerating_report_supersedes_without_deleting_blob`
- `test_created_at_immutable_after_creation`
- `test_updated_at_changes_on_supersede`
- `test_full_version_history_of_report_is_retrievable`

## Implementation Notes

- Affected files: modelo `Report`, endpoints en `backend-api`, tool `generate_report` en
  `audit-tools` (spec-012).
- Dependencies: guardrail hard-block `DELETE FROM (audit_trail|audit_findings|findings|reports)`
  en `.ai/guardrails/restricted-ops.json` (mismo mecanismo que spec-004, extendido a `reports`).
- Quick Rules referenced: `audit-domain-rules` (reglas 3, 5), `fastapi` (regla 6).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [audit-domain-rules/SKILL.md](../../skills/audit-domain-rules/SKILL.md)
- [fastapi/SKILL.md](../../skills/fastapi/SKILL.md)

### Specs Relacionadas
- [spec-004-inmutabilidad-audit-trail.md](spec-004-inmutabilidad-audit-trail.md) — mismo contrato,
  aplicado a `reports` en vez de `findings`/`audit_trail`.

### Archivo de Test
- `tests/specs/test_spec_011_inmutabilidad_reportes.py`
