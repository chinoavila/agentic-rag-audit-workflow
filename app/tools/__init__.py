"""Audit tools invocable by LLM (tool-calling/function-calling).

`agentic-core` debe importar `CREATE_FINDING_TOOL_SPEC` (o `create_finding`/`input_schema`
directo) para declarar la tool ante la API del LLM vía el parámetro `tools`/`input_schema`
correspondiente — nunca reescribir esta documentación como texto libre dentro del system
prompt (`.ai/skills/agentic-tool-use/SKILL.md` regla 4).
"""

from app.tools.create_finding import (
    CreateFindingInput,
    calculate_risk_score,
    create_finding,
    input_schema as create_finding_input_schema,
)
from app.tools.generate_report import (
    GenerateReportInput,
    generate_report,
    input_schema as generate_report_input_schema,
)

# Declaración lista para pasar tal cual al parámetro `tools=[...]` de la API del LLM
# (formato compatible con Anthropic/OpenAI function-calling: name/description/input_schema).
CREATE_FINDING_TOOL_SPEC: dict = {
    "name": "create_finding",
    "description": (
        "Crea un hallazgo de auditoría con severidad (low|medium|high|critical) y al menos "
        "una cita de evidencia {source, page}. Calcula risk_score automáticamente. Hallazgos "
        "high/critical quedan en status=pending_review (requieren aprobación humana antes de "
        "pasar a final, spec-006). Idempotente: reintentar con el mismo case_id+title+evidence "
        "no duplica el hallazgo."
    ),
    "input_schema": create_finding_input_schema,
}

GENERATE_REPORT_TOOL_SPEC: dict = {
    "name": "generate_report",
    "description": (
        "Genera un informe de auditoría a partir de una plantilla ya indexada, completando "
        "únicamente sus placeholders de prosa con narrativa que cita evidencia de hallazgos "
        "ya registrados en el caso. Corre rúbricas automáticas (completitud, citas válidas, "
        "formato) antes de persistir: si fallan, no se crea ningún informe y se devuelve "
        "feedback estructurado para reintentar con secciones corregidas. Si pasa, el informe "
        "queda en status=pending_review: requiere aprobación humana explícita antes de poder "
        "publicarse (spec-006)."
    ),
    "input_schema": generate_report_input_schema,
}

__all__ = [
    "CreateFindingInput",
    "calculate_risk_score",
    "create_finding",
    "create_finding_input_schema",
    "CREATE_FINDING_TOOL_SPEC",
    "GenerateReportInput",
    "generate_report",
    "generate_report_input_schema",
    "GENERATE_REPORT_TOOL_SPEC",
]
