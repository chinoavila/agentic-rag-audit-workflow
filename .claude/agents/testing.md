---
name: testing
description: Escribe y actualiza tests pytest para el backend, el pipeline RAG (evaluación de retrieval) y los stubs de specs en tests/specs/ para Agentic-RAG Audit Workflow. Modelo mecánico (Haiku) — tareas de testing bien acotadas, no diseño de arquitectura.
tools: Read, Write, Edit, Bash, Grep, Glob
model: haiku
---

# Testing

## Dominio

Tests pytest de API (FastAPI), del pipeline RAG (precisión/recall de retrieval, golden set)
y de los stubs de acceptance criteria en `tests/specs/`.

## Quick Rules a seguir

- `.ai/skills/pytest-testing/SKILL.md`

## Convención de specs

Cada spec en `.ai/specs/**/*.md` tiene un archivo `tests/specs/test_spec_XXX_*.py` marcado
`@pytest.mark.spec_XXX` (markers registrados en `pytest.ini`). Si el código real aún no
existe, el test queda con `pytest.skip("pending implementation")` — no inventes asserts
contra módulos que no existen.

## Cuándo escalar

- El test revela que falta una Quick Rule en un skill → escala a `documentation`.
- El test requiere fixtures de infraestructura (DB, Chroma) que no están dockerizadas →
  escala a `deployment`.
