#!/bin/bash
# .claude/hooks/session-init.sh (referencia Unix; el harness principal corre en PowerShell/Windows)
# SessionStart: inyecta contexto de la sesion via hookSpecificOutput.additionalContext.
# Requiere `jq`.

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "no-git")
CHANGES=$(git status --short 2>/dev/null | wc -l)
DOCKER=$(docker compose ps 2>/dev/null | wc -l)

CONTEXT="SESSION INIT
Branch: $BRANCH
Cambios sin commitear: $CHANGES
Contenedores Docker activos: $DOCKER
SSOT: .ai/ (skills, specs, guardrails, handoffs) | Agentes ejecutables: .claude/agents/"

jq -n --arg ctx "$CONTEXT" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'

exit 0
