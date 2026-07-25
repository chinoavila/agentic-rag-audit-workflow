---
name: audit-tools
description: Implementa las herramientas de auditoría invocables por el LLM (registro de hallazgos, taxonomía de severidad, evidencia, risk scoring) para Agentic-RAG Audit Workflow. Usar para lógica de negocio de auditoría, no para el loop del agente en sí.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

# Audit Tools

## Dominio

Las funciones/tools de dominio de auditoría que el `agentic-core` expone al LLM: crear
hallazgo, clasificar severidad, adjuntar evidencia, calcular risk score, marcar hallazgo
como superseded.

## Quick Rules a seguir

- `.ai/skills/audit-domain-rules/SKILL.md`

## Specs que debes satisfacer

- `.ai/specs/audit/spec-003-invocacion-segura-tools.md`
- `.ai/specs/audit/spec-004-inmutabilidad-audit-trail.md` — nunca `DELETE`, solo `superseded_by`
- `.ai/specs/audit/spec-006-human-in-the-loop.md` — severidad alta/crítica requiere aprobación humana antes de `status=final`

## Cuándo escalar

- Necesita persistir el hallazgo en la base de datos → escala a `backend-api`.
- La aprobación humana de un hallazgo de alto riesgo no está implementada aún → escala a
  `security-compliance` para definir el flujo de aprobación antes de continuar.
- El hallazgo necesita mostrarse con acciones (aprobar/rechazar) en el chat → coordina con
  `chainlit-ui`.
