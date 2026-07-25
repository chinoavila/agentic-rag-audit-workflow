# Audit Domain Rules — Quick Rules

**Versión**: 1.0
**Última actualización**: 2026-07-24

## ⚡ Quick Rules (Verificables, No Negociables)

1. **Taxonomía de severidad cerrada**: `low | medium | high | critical`, sin valores libres.
   - ✅ OK: `severity: Literal["low", "medium", "high", "critical"]`
   - ❌ BAD: `severity: str` libre (permite "urgente", "grave", etc. sin normalizar)
   - 🔍 Verificar: el tipo de `severity` está restringido a los 4 valores.

2. **Evidencia obligatoria en todo hallazgo**: un hallazgo sin al menos una cita/fuente no
   es válido (spec-001).
   - ✅ OK: `Finding(evidence=[Citation(source=..., page=...)])`
   - ❌ BAD: `Finding(evidence=[])`
   - 🔍 Verificar: `evidence` no está vacío al crear un hallazgo.

3. **Audit trail append-only** (spec-004): ningún hallazgo se borra; se marca
   `superseded_by=<nuevo_id>` y el original permanece con su `id` intacto.
   - ✅ OK: `finding.superseded_by = new_finding.id`
   - ❌ BAD: `db.delete(finding)`
   - 🔍 Verificar: no existe ningún `DELETE`/`db.delete` sobre hallazgos o el audit trail.

4. **Human-in-the-loop para severidad alta/crítica** (spec-006): un hallazgo `high` o
   `critical` no puede pasar a `status=final` sin un registro de aprobación humana
   (`approved_by`, `approved_at`).
   - ✅ OK: `if severity in ("high","critical") and not approved_by: status = "pending_review"`
   - ❌ BAD: marcar `status="final"` automáticamente sin importar la severidad
   - 🔍 Verificar: existe la transición `pending_review → final` condicionada a aprobación.

5. **Timestamps inmutables de creación**: `created_at` nunca se modifica tras crear el
   hallazgo; `updated_at` se actualiza en cada cambio de estado (incluyendo supersede).
   - 🔍 Verificar: `created_at` no aparece en ningún `UPDATE`.

6. **Risk scoring determinista y explicable**: el cálculo de `risk_score` es una función pura
   documentada (no un número mágico sin trazabilidad de cómo se llegó a él).
   - 🔍 Verificar: existe una función nombrada (`calculate_risk_score`) con inputs explícitos.

---

## 📚 Guía completa

- Un "caso de auditoría" agrupa hallazgos; un hallazgo pertenece a exactamente un caso.
- Ver `.ai/specs/audit/` para las specs completas (spec-003, spec-004, spec-006).
