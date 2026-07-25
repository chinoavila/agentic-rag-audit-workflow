#!/bin/bash
# .claude/hooks/route-agent.sh (referencia Unix; el harness principal corre en PowerShell/Windows)
# UserPromptSubmit: routing por keywords, sin llamada a LLM. Recibe {"prompt": "..."} por stdin.
# Un hook no puede invocar un subagente directamente -- inyecta una sugerencia via
# hookSpecificOutput.additionalContext, que el modelo principal lee como contexto del turno.
# Requiere `jq`.

set -euo pipefail

PAYLOAD="$(cat)"
PROMPT="$(echo "$PAYLOAD" | jq -r '.prompt // empty')"

[ -z "$PROMPT" ] && exit 0

declare -A ROUTES=(
    ["prompt.?injection|contenido no confiable|PII|dato sensible|trazabilidad|human.?in.?the.?loop|audit trail|inmutab"]="security-compliance"
    ["chainlit|cl\.Step|action button|chat profile|interfaz de chat"]="chainlit-ui"
    ["hallazgo|severidad|evidencia|control de auditoria|risk scoring|auditoria"]="audit-tools"
    ["ingest|chunk|embedding|chroma|faiss|reindex|vector ?store|retrieval"]="rag-engineer"
    ["tool.?use|function.?calling|system prompt|agentic loop"]="agentic-core"
    ["endpoint|FastAPI|router|schema pydantic|API REST"]="backend-api"
    ["test|pytest|coverage|golden set"]="testing"
    ["deploy|docker|contenedor"]="deployment"
    ["docs|documentacion|README|SKILL.md"]="documentation"
)

# El orden de asociativos no esta garantizado en bash; se prioriza por especificidad manualmente
ORDER=(
    "prompt.?injection|contenido no confiable|PII|dato sensible|trazabilidad|human.?in.?the.?loop|audit trail|inmutab"
    "chainlit|cl\.Step|action button|chat profile|interfaz de chat"
    "hallazgo|severidad|evidencia|control de auditoria|risk scoring|auditoria"
    "ingest|chunk|embedding|chroma|faiss|reindex|vector ?store|retrieval"
    "tool.?use|function.?calling|system prompt|agentic loop"
    "endpoint|FastAPI|router|schema pydantic|API REST"
    "test|pytest|coverage|golden set"
    "deploy|docker|contenedor"
    "docs|documentacion|README|SKILL.md"
)

DETECTED=""
for pattern in "${ORDER[@]}"; do
    if echo "$PROMPT" | grep -iqE "$pattern"; then
        DETECTED="${ROUTES[$pattern]}"
        break
    fi
done

if [ -n "$DETECTED" ]; then
    jq -n --arg ctx "route-agent: este prompt matchea keywords del dominio '$DETECTED'. Considera usar el agente '$DETECTED' (Agent tool, subagent_type=$DETECTED) para esta tarea, salvo que el contexto de la conversacion indique otra cosa." \
        '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
fi

exit 0
