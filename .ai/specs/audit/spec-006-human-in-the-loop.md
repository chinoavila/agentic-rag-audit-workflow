# Spec: Human-in-the-Loop para Hallazgos de Alto Riesgo (spec-006)

## Summary
Ningún hallazgo de severidad `high` o `critical` puede marcarse como `status=final` sin
que un humano lo haya aprobado explícitamente. El agente puede proponer, pero no cerrar
solo, decisiones de alto impacto.

## Acceptance Criteria

- [ ] Un hallazgo `high`/`critical` creado por el agente entra en `status=pending_review`,
      nunca directo a `final`.
- [ ] La transición `pending_review → final` requiere `approved_by` (id de usuario humano) y
      `approved_at` (timestamp) no nulos.
- [ ] Un hallazgo `low`/`medium` puede pasar a `final` sin aprobación humana explícita
      (el umbral de severidad decide si aplica el gate).
- [ ] La UI (Chainlit) expone una acción explícita de aprobar/rechazar para hallazgos en
      `pending_review` (no se aprueba por texto libre interpretado).
- [ ] Rechazar un hallazgo en `pending_review` lo marca `superseded_by`/`status=rejected`
      sin perder el registro (ver spec-004).

## Test Cases

- `test_high_severity_finding_starts_as_pending_review`
- `test_final_transition_requires_approved_by_and_approved_at`
- `test_low_severity_finding_can_reach_final_without_approval`
- `test_chainlit_exposes_approve_reject_action_for_pending_review`
- `test_rejected_finding_preserves_record`

## Implementation Notes

- Affected files: modelo `Finding` (state machine), `audit-tools`, acciones en `chainlit-ui`.
- Dependencies: spec-004 (inmutabilidad), skill `audit-domain-rules` (regla 4), skill
  `chainlit` (regla 4).
- Quick Rules referenced: `audit-domain-rules` (regla 4), `chainlit` (regla 4).

---

## Referencias Cruzadas

### Quick Rules Relacionadas
- [audit-domain-rules/SKILL.md](../../skills/audit-domain-rules/SKILL.md)
- [chainlit/SKILL.md](../../skills/chainlit/SKILL.md)

### Archivo de Test
- `tests/specs/test_spec_006_human_in_the_loop.py`
