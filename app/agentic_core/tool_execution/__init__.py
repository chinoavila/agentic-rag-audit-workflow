"""Ejecución sandboxed de comandos reales resueltos desde una allowlist versionada (spec-015).

Ver:
- `allowlist.py`: mapa versionado `(tool_key, action_id) -> argv fijo + schema de params`
  (spec-015, punto 1). `ToolCatalogEntry.actions[].command` sigue siendo, sin excepción,
  texto descriptivo para humanos -- nunca se lee ni se ejecuta acá.
- `sandbox.py`: ejecutor aislado (env explícito nunca heredado, límites de recursos,
  timeout duro) que resuelve `(tool_key, action_id, params)` contra la allowlist antes de
  correr nada (spec-015, puntos 2-3). Documenta explícitamente, sin ocultarla, la limitación
  real de aislamiento de red en este contenedor no-privilegiado.

Este paquete es el entregable de la Task 9 del plan de permission modes
(`docs/plans/plan-tool-execution-permission-modes.md`) -- el mecanismo de sandboxing que la
Task 10 (backend-api, endpoints de `ToolRun`, aún no implementada) debe invocar antes de
cualquier transición `proposed -> executed`/`failed`. Ningún otro módulo del backend debe
ejecutar un `ToolCatalogEntry.actions[].command` por fuera de `sandbox.execute()` (spec-015,
punto 4: el sandbox aplica sin excepción, ninguna metadata del catálogo exime).
"""

from app.agentic_core.tool_execution.sandbox import execute

__all__ = ["execute"]
