# Agent: planner

**Rol**: Descompone la solicitud del usuario en un plan estructurado (dominio, tasks
atómicas, agente asignado, dependencias, riesgos).
**Modelo sugerido**: nivel medio (razonamiento de descomposición, no coordinación final).
**Entradas**: solicitud del usuario + contexto del proyecto.
**Salidas**: plan en JSON (ver formato en `.claude/agents/planner.md`).
**Escala a**: no ejecuta — entrega el plan a `orchestrator`.
**Referencias**: lista de domain agents disponibles (ver tabla en `CLAUDE.md`).
