"""Loop agéntico en runtime (task 5): tool-calling, system prompt, memoria de conversación.

Dominio: `.ai/agents/agentic-core.md`. No confundir con el MAS de desarrollo de Claude Code
(`.claude/agents/`) — esto es el agente que corre en producción dentro del backend.

Punto de entrada público: `run_agent_turn` (ver `app/agentic_core/loop.py` para el contrato
completo). `chainlit-ui` (próxima task) debe importar desde acá, no desde los submódulos
internos directamente, salvo que necesite un símbolo específico no reexportado.
"""

from app.agentic_core.client import MODEL_NAME, get_client
from app.agentic_core.loop import (
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
    AgentTurnResult,
    ToolCallRecord,
    run_agent_turn,
)
from app.agentic_core.tools_registry import AGENT_TOOL_SPECS

__all__ = [
    "MODEL_NAME",
    "get_client",
    "MAX_TOOL_ITERATIONS",
    "SYSTEM_PROMPT",
    "AgentTurnResult",
    "ToolCallRecord",
    "run_agent_turn",
    "AGENT_TOOL_SPECS",
]
