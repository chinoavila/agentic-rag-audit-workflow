# .claude/hooks/pre-tool-guard.ps1
# PreToolUse: bloquea operaciones destructivas leyendo la SSOT de guardrails (.ai/guardrails/restricted-ops.json).
# Contrato real de Claude Code: recibe {"tool_name":..., "tool_input":{...}} por stdin,
# responde bloqueo/advertencia via JSON en stdout (hookSpecificOutput.permissionDecision).
# Script deterministico (regex sobre JSON), sin llamada a LLM.

$ErrorActionPreference = "Stop"

function Write-HookJson($obj) {
    $obj | ConvertTo-Json -Depth 8 -Compress
}

try {
    $stdin = [Console]::In.ReadToEnd()
    $payload = $stdin | ConvertFrom-Json
} catch {
    # Payload ilegible: no podemos evaluar, no bloqueamos una operacion que no entendemos.
    exit 0
}

$toolName = $payload.tool_name
$toolInput = $payload.tool_input

switch ($toolName) {
    "Bash" { $commandStr = "$toolName $($toolInput.command)" }
    "PowerShell" { $commandStr = "$toolName $($toolInput.command)" }
    "Edit" { $commandStr = "$toolName $($toolInput.file_path) $($toolInput.new_string)" }
    "Write" { $commandStr = "$toolName $($toolInput.file_path) $($toolInput.content)" }
    default { $commandStr = "$toolName $($toolInput | ConvertTo-Json -Compress -Depth 10)" }
}

$guardrailsPath = Join-Path $PSScriptRoot "..\..\.ai\guardrails\restricted-ops.json"
if (-not (Test-Path $guardrailsPath)) {
    exit 0
}

$guardrails = Get-Content $guardrailsPath -Raw | ConvertFrom-Json

foreach ($block in $guardrails.blocked_hard) {
    if ($commandStr -match $block.pattern) {
        $reason = "BLOQUEADO: $($block.pattern) -- $($block.reason). Alternativa: $($block.alternative)"
        Write-HookJson @{
            hookSpecificOutput = @{
                hookEventName            = "PreToolUse"
                permissionDecision       = "deny"
                permissionDecisionReason = $reason
            }
        }
        exit 0
    }
}

$warnings = @()
foreach ($warn in $guardrails.blocked_soft_warning) {
    if ($commandStr -match $warn.pattern) {
        $warnings += $warn.message
    }
}

if ($warnings.Count -gt 0) {
    Write-HookJson @{
        systemMessage      = "ADVERTENCIA: " + ($warnings -join " | ")
        hookSpecificOutput = @{
            hookEventName      = "PreToolUse"
            permissionDecision = "allow"
        }
    }
}

exit 0
