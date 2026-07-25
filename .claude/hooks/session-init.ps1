# .claude/hooks/session-init.ps1
# SessionStart: inyecta contexto de la sesion (branch, cambios, docker) sin costo de tokens LLM.
# Contrato real de Claude Code: la forma garantizada de inyectar contexto es
# hookSpecificOutput.additionalContext en la salida JSON (no una variable de entorno del proceso hijo).

$ErrorActionPreference = "SilentlyContinue"

$branch = git rev-parse --abbrev-ref HEAD 2>$null
if (-not $branch) { $branch = "no-git" }

$changes = (git status --short 2>$null | Measure-Object -Line).Lines
$dockerUp = (docker compose ps 2>$null | Measure-Object -Line).Lines

$context = @"
SESSION INIT
Branch: $branch
Cambios sin commitear: $changes
Contenedores Docker activos: $dockerUp
SSOT: .ai/ (skills, specs, guardrails, handoffs) | Agentes ejecutables: .claude/agents/
"@

@{
    hookSpecificOutput = @{
        hookEventName     = "SessionStart"
        additionalContext = $context
    }
} | ConvertTo-Json -Depth 5 -Compress

exit 0
