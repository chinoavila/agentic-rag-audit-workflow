# Agent: orchestrator

**Rol**: Coordina el flujo PEV (Planner → Executor → Reviewer) de 6 pasos. Punto de entrada
por defecto.
**Modelo sugerido**: nivel más capaz disponible (razonamiento/coordinación).
**Entradas**: solicitud del usuario en lenguaje natural.
**Salidas**: plan aprobado, artefactos ejecutados, reporte final.
**Escala a**: `planner` (paso 1), cualquier domain agent (paso 4), `reviewer` (paso 5).
**Referencias**: `.ai/handoffs/escalation-map.md`, todas las skills y specs (indirectamente,
vía los domain agents).
