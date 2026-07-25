# .claude/hooks/route-agent.ps1
# UserPromptSubmit: routing por keywords, sin llamada a LLM (costo cero de tokens).
# Contrato real de Claude Code: recibe {"prompt": "..."} por stdin. Un hook no puede invocar
# un subagente directamente -- inyecta una sugerencia via hookSpecificOutput.additionalContext,
# que el modelo principal lee como contexto adicional del turno.
# Orden = prioridad: el primer patron que matchea gana. Mas especifico primero.

$ErrorActionPreference = "Stop"

try {
    $stdin = [Console]::In.ReadToEnd()
    $payload = $stdin | ConvertFrom-Json
} catch {
    exit 0
}

$prompt = $payload.prompt
if (-not $prompt) { exit 0 }

$routes = [ordered]@{
    "prompt.?injection|contenido no confiable|PII|dato sensible|trazabilidad|human.?in.?the.?loop|audit trail|inmutab"   = "security-compliance"
    "chainlit|cl\.Step|action button|chat profile|streaming del chat|interfaz de chat|UI conversacional"                 = "chainlit-ui"
    "hallazgo|severidad|evidencia|control de auditor[ií]a|risk scoring|compliance check|auditor[ií]a"                    = "audit-tools"
    "ingest|ingesta|chunk|embedding|chroma|faiss|reindex|vector ?store|retrieval|recuperaci[oó]n de documentos"          = "rag-engineer"
    "tool.?use|function.?calling|system prompt|loop del agente|memoria de conversaci[oó]n|agentic loop|orquestaci[oó]n del LLM" = "agentic-core"
    "endpoint|FastAPI|router|schema pydantic|API REST|auth endpoint"                                                     = "backend-api"
    "test|pytest|coverage|golden set|eval de retrieval"                                                                  = "testing"
    "deploy|docker|docker-compose|contenedor"                                                                            = "deployment"
    "docs|documentaci[oó]n|README|SKILL\.md"                                                                             = "documentation"
}

$detected = $null
foreach ($pattern in $routes.Keys) {
    if ($prompt -match $pattern) {
        $detected = $routes[$pattern]
        break
    }
}

if ($detected) {
    $context = "route-agent: este prompt matchea keywords del dominio '$detected'. Considera usar el agente '$detected' (Agent tool, subagent_type=$detected) para esta tarea, salvo que el contexto de la conversacion indique otra cosa."
    @{
        hookSpecificOutput = @{
            hookEventName   = "UserPromptSubmit"
            additionalContext = $context
        }
    } | ConvertTo-Json -Depth 5 -Compress
}

exit 0
