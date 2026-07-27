# `.ai/` — Single Source of Truth (SSOT)

Esta carpeta es la **única fuente real** de skills, specs, guardrails y handoffs del
proyecto **Agentic-RAG Audit Workflow**. No se duplica en ningún otro lugar:

- `.claude/hooks/pre-tool-guard.ps1` **lee** `.ai/guardrails/restricted-ops.json` en runtime.
- Los agentes en `.claude/agents/*.md` **referencian** rutas de `.ai/skills/` y `.ai/specs/`
  en su prompt, en vez de copiar su contenido.
- `.ai/agents/*.md` es un espejo agnóstico (sin frontmatter de Claude Code) de cada agente,
  pensado para portar el mismo diseño a otras herramientas (Copilot, Cursor, etc.) si hiciera
  falta — no es una copia del prompt completo de `.claude/agents/`.

Enforcement en 3 capas (prototipo de despliegue manual, sin CI): **Hooks → Guardrails →
Reviewer**.

## Índice

### Agentes (espejo agnóstico — ver `.claude/agents/` para la versión ejecutable)
[orchestrator](agents/orchestrator.md) · [planner](agents/planner.md) ·
[reviewer](agents/reviewer.md) · [rag-engineer](agents/rag-engineer.md) ·
[agentic-core](agents/agentic-core.md) · [audit-tools](agents/audit-tools.md) ·
[backend-api](agents/backend-api.md) · [chainlit-ui](agents/chainlit-ui.md) ·
[security-compliance](agents/security-compliance.md) · [testing](agents/testing.md) ·
[deployment](agents/deployment.md) · [documentation](agents/documentation.md)

### Skills (Quick Rules)
| Skill | Usado por |
|---|---|
| [fastapi](skills/fastapi/SKILL.md) | `backend-api` |
| [chainlit](skills/chainlit/SKILL.md) | `chainlit-ui` |
| [rag-ingestion](skills/rag-ingestion/SKILL.md) | `rag-engineer` |
| [rag-retrieval](skills/rag-retrieval/SKILL.md) | `rag-engineer` |
| [vectorstore-chroma-faiss](skills/vectorstore-chroma-faiss/SKILL.md) | `rag-engineer` |
| [agentic-tool-use](skills/agentic-tool-use/SKILL.md) | `agentic-core` |
| [audit-domain-rules](skills/audit-domain-rules/SKILL.md) | `audit-tools` |
| [security-prompt-injection](skills/security-prompt-injection/SKILL.md) | `security-compliance` |
| [pytest-testing](skills/pytest-testing/SKILL.md) | `testing` |
| [docker-deployment](skills/docker-deployment/SKILL.md) | `deployment` |

### Specs SDD (ver [SPEC_TEMPLATE.md](specs/SPEC_TEMPLATE.md))
| Spec | Carpeta | Test | Estado |
|---|---|---|---|
| spec-001 Grounding & Citación obligatoria | `specs/rag/` | `tests/specs/test_spec_001_*.py` | ✅ |
| spec-002 Ingesta idempotente | `specs/rag/` | `tests/specs/test_spec_002_*.py` | ✅ |
| spec-003 Invocación segura de tools | `specs/audit/` | `tests/specs/test_spec_003_*.py` | ✅ |
| spec-004 Inmutabilidad del audit trail | `specs/audit/` | `tests/specs/test_spec_004_*.py` | ✅ |
| spec-005 Defensa anti prompt-injection | `specs/rag/` | `tests/specs/test_spec_005_*.py` | ✅ |
| spec-006 Human-in-the-loop | `specs/audit/` | `tests/specs/test_spec_006_*.py` | ✅ |
| spec-007 Aislamiento de sesión/auth | `specs/platform/` | `tests/specs/test_spec_007_*.py` | ❌ pendiente |
| spec-008 Umbral de relevancia | `specs/rag/` | `tests/specs/test_spec_008_*.py` | ✅ |
| spec-009 Entorno Docker reproducible | `specs/platform/` | `tests/specs/test_spec_009_*.py` | ✅ |
| spec-010 Contrato de error de API | `specs/platform/` | `tests/specs/test_spec_010_*.py` | ✅ |
| spec-011 Inmutabilidad de reportes generados | `specs/audit/` | `tests/specs/test_spec_011_*.py` | ✅ |
| spec-012 Generación de informes desde plantilla | `specs/audit/` | `tests/specs/test_spec_012_*.py` | ✅ |
| spec-013 Exposición dinámica de tools vía retrieval | `specs/rag/` | `tests/specs/test_spec_013_*.py` | ❌ pendiente |

El código también referencia specs informales (014, 017, 018, 020 — migración a frontend
React: chats/proyectos persistentes, catálogo de tools, exportación de informes) sin spec doc
SDD ni test spec dedicados todavía; ver comentarios en `app/models/*` y `app/routers/*`.

### Guardrails y Handoffs
- [guardrails/restricted-ops.json](guardrails/restricted-ops.json) — bloqueos hard/soft, consumido por `.claude/hooks/pre-tool-guard.ps1`
- [handoffs/escalation-map.md](handoffs/escalation-map.md) — cuándo un agente escala a otro

## Estado de los tests

- **70 tests pasando, 9 skipped intencionales** (los 9 skips son íntegramente spec-007 y
  spec-013, las únicas dos specs formales aún sin implementar).

Comando para ejecutar la suite completa:
```bash
docker compose run --rm backend python -m pytest
```

Ver tabla de estado en [`../docs/sdd-status.md`](../docs/sdd-status.md) para detalles de
implementación por spec, y [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) para los
diagramas de arquitectura.
