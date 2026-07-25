#!/bin/bash
# .claude/hooks/pre-tool-guard.sh (referencia Unix; el harness principal corre en PowerShell/Windows)
# PreToolUse: bloquea operaciones destructivas leyendo la SSOT de guardrails (.ai/guardrails/restricted-ops.json).
# Contrato real de Claude Code: recibe {"tool_name":..., "tool_input":{...}} por stdin,
# responde bloqueo/advertencia via JSON en stdout (hookSpecificOutput.permissionDecision).
# Requiere `jq`.

set -euo pipefail

PAYLOAD="$(cat)"
TOOL_NAME="$(echo "$PAYLOAD" | jq -r '.tool_name // empty')"

case "$TOOL_NAME" in
    Bash|PowerShell)
        COMMAND_STR="$TOOL_NAME $(echo "$PAYLOAD" | jq -r '.tool_input.command // empty')"
        ;;
    Edit)
        COMMAND_STR="$TOOL_NAME $(echo "$PAYLOAD" | jq -r '.tool_input.file_path // empty') $(echo "$PAYLOAD" | jq -r '.tool_input.new_string // empty')"
        ;;
    Write)
        COMMAND_STR="$TOOL_NAME $(echo "$PAYLOAD" | jq -r '.tool_input.file_path // empty') $(echo "$PAYLOAD" | jq -r '.tool_input.content // empty')"
        ;;
    *)
        COMMAND_STR="$TOOL_NAME $(echo "$PAYLOAD" | jq -c '.tool_input // {}')"
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARDRAILS_PATH="$SCRIPT_DIR/../../.ai/guardrails/restricted-ops.json"

if [ ! -f "$GUARDRAILS_PATH" ]; then
    exit 0
fi

HARD_COUNT="$(jq '.blocked_hard | length' "$GUARDRAILS_PATH")"
for i in $(seq 0 $((HARD_COUNT - 1))); do
    PATTERN="$(jq -r ".blocked_hard[$i].pattern" "$GUARDRAILS_PATH")"
    if echo "$COMMAND_STR" | grep -qE "$PATTERN"; then
        REASON="$(jq -r ".blocked_hard[$i].reason" "$GUARDRAILS_PATH")"
        ALTERNATIVE="$(jq -r ".blocked_hard[$i].alternative" "$GUARDRAILS_PATH")"
        jq -n --arg reason "BLOQUEADO: $PATTERN -- $REASON. Alternativa: $ALTERNATIVE" \
            '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
        exit 0
    fi
done

WARNINGS=()
WARN_COUNT="$(jq '.blocked_soft_warning | length' "$GUARDRAILS_PATH")"
for i in $(seq 0 $((WARN_COUNT - 1))); do
    PATTERN="$(jq -r ".blocked_soft_warning[$i].pattern" "$GUARDRAILS_PATH")"
    if echo "$COMMAND_STR" | grep -qE "$PATTERN"; then
        WARNINGS+=("$(jq -r ".blocked_soft_warning[$i].message" "$GUARDRAILS_PATH")")
    fi
done

if [ "${#WARNINGS[@]}" -gt 0 ]; then
    JOINED=$(IFS=" | "; echo "${WARNINGS[*]}")
    jq -n --arg msg "ADVERTENCIA: $JOINED" \
        '{systemMessage: $msg, hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "allow"}}'
fi

exit 0
