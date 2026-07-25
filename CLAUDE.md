# Agentic-RAG Audit Workflow

Interfaz de chat conversacional (Chainlit) respaldada por un backend agéntico (FastAPI) que
combina RAG (Chroma/FAISS) sobre documentos de auditoría con herramientas de auditoría
invocables por el LLM (tool-use). Prototipo de despliegue local manual vía Docker Compose.

## Stack

- **UI conversacional**: Chainlit
- **Backend**: Python + FastAPI
- **RAG**: Chroma/FAISS local
- **Orquestación del agente**: tool-calling/function-calling sobre el LLM (ver `.ai/skills/agentic-tool-use`)

## 🔧 Harness Engineering

### Hooks automáticos (`.claude/hooks/`)
- **SessionStart** (`session-init.ps1`): inyecta branch, cambios sin commitear, estado de Docker.
- **UserPromptSubmit** (`route-agent.ps1`): routing automático por keywords hacia el agente de dominio correcto (ver tabla de agentes abajo). Sin costo de LLM.
- **PreToolUse** (`pre-tool-guard.ps1`): bloquea operaciones destructivas leyendo `.ai/guardrails/restricted-ops.json`.

### Guardrails (`.ai/guardrails/restricted-ops.json`)
Bloqueos duros:
- `git reset --hard` → usar `git stash`
- `npm/pip install` en host → `docker compose exec <servicio> ...`
- `rm -rf` → `git clean -fd`
- `docker compose down -v` → pierde el índice RAG y el audit trail; usar sin `-v`
- `DELETE FROM audit_trail/audit_findings` → el audit trail es **append-only**; usar `superseded_by`
- Commitear `.env`/API keys

Advertencias suaves: `git commit`/`git push` sin `--dry-run`, bajar el umbral de similitud de retrieval, subir `max_tool_iterations`, cambios en la ruta de persistencia de Chroma.

### Model assignment
- **Orchestrator**: Claude Opus 4.8 (coordinación, juicio)
- **Domain agents** (rag-engineer, agentic-core, audit-tools, backend-api, chainlit-ui, security-compliance, planner, reviewer): Claude Sonnet 5
- **Mechanical** (testing, deployment, documentation): Claude Haiku 4.5

## 🤖 Agentes (MAS) — ver `.claude/agents/` y espejo agnóstico en `.ai/agents/`

| Agente | Dominio |
|---|---|
| `orchestrator` | Coordina el flujo PEV (Planner→Executor→Reviewer) y el routing final |
| `planner` | Descompone la solicitud del usuario en un plan estructurado |
| `reviewer` | Valida artefactos generados contra las Quick Rules de cada skill |
| `rag-engineer` | Ingesta, chunking, embeddings, retrieval y reranking (Chroma/FAISS) |
| `agentic-core` | Loop del agente en runtime: tool-calling, system prompt, memoria de conversación |
| `audit-tools` | Herramientas de auditoría invocables por el LLM (hallazgos, severidad, evidencia) |
| `backend-api` | Endpoints FastAPI (auth, casos de auditoría, carga de evidencia) |
| `chainlit-ui` | UI conversacional Chainlit (streaming, steps, actions, sesión) |
| `security-compliance` | Prompt injection vía documentos, PII, trazabilidad, human-in-the-loop |
| `testing` | pytest para backend/RAG, evaluación de retrieval |
| `deployment` | Docker/docker-compose, configuración de entorno |
| `documentation` | Mantiene sincronizados SKILL.md, specs y READMEs |

## 🔄 Flujo PEV (Planner → Executor → Reviewer)

1. **Analizar** (Planner): identifica dominio y genera plan estructurado.
2. **Confirmar** (Orchestrator → Usuario): presenta el plan, espera aprobación.
3. **Evaluar** (Orchestrator): revisa riesgos y completitud del plan.
4. **Ejecutar** (Domain Agents): cada agente ejecuta su tarea y genera artefactos.
5. **Verificar** (Reviewer): valida contra Quick Rules; si rechaza, hay loop de re-ejecución con feedback.
6. **Reportar** (Orchestrator): resumen de cambios, archivos y próximos pasos.

Detalle completo del loop de re-ejecución en [`.claude/agents/orchestrator.md`](.claude/agents/orchestrator.md).

## 📚 SSOT (Single Source of Truth) — `.ai/`

Skills, specs, guardrails y handoffs viven **únicamente** en `.ai/` (no se duplican). Los agentes
(`.claude/agents/*.md`) referencian esas rutas directamente en su prompt en vez de copiar su contenido.

```
.ai/
  agents/        # espejo agnóstico de cada agente (sin frontmatter de Claude Code)
  skills/        # Quick Rules verificables por skill (SKILL.md)
  specs/         # specs SDD ejecutables (rag/, audit/, platform/)
  guardrails/    # restricted-ops.json (fuente única, consumida por los hooks)
  handoffs/      # escalation-map.md — cuándo un agente escala a otro
```

**Enforcement en 3 capas** (sin CI, es un prototipo de despliegue manual): Hooks + Guardrails + Reviewer.

Ver [`.ai/README.md`](.ai/README.md) para el índice completo.
