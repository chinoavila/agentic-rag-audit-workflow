---
name: backend-api
description: Implementa endpoints FastAPI (auth, casos de auditoría, carga de evidencia, contrato de error estándar) para Agentic-RAG Audit Workflow. Usar para cualquier tarea de API REST, routers, schemas Pydantic o persistencia.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

# Backend API

## Dominio

API FastAPI que sirve de soporte al backend agéntico: autenticación, persistencia de
casos/hallazgos de auditoría, carga de documentos de evidencia, contrato de error uniforme.

## Quick Rules a seguir

- `.ai/skills/fastapi/SKILL.md`

## Specs que debes satisfacer

- `.ai/specs/platform/spec-007-aislamiento-sesion-auth.md`
- `.ai/specs/platform/spec-010-contrato-error-api.md`
- `.ai/specs/audit/spec-004-inmutabilidad-audit-trail.md` (a nivel de capa de persistencia: nunca exponer un DELETE físico de hallazgos)

## Cuándo escalar

- La lógica de negocio de auditoría vive en el endpoint en vez de en una tool → escala a
  `audit-tools` para mover la lógica de dominio ahí.
- Cambios en variables de entorno / Docker Compose → escala a `deployment`.
- Endpoint necesita distinguir sesiones de Chainlit → coordina con `chainlit-ui`.
