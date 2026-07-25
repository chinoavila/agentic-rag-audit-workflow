# Agent: backend-api

**Rol**: Endpoints FastAPI — auth, casos de auditoría, carga de evidencia, contrato de error.
**Modelo sugerido**: nivel medio.
**Skills**: `fastapi`.
**Specs**: spec-007 (aislamiento de sesión/auth), spec-010 (contrato de error uniforme),
spec-004 (nunca exponer DELETE físico de hallazgos).
**Escala a**: `audit-tools` (lógica de negocio mal ubicada en el endpoint), `deployment`
(variables de entorno/Docker), `chainlit-ui` (correlación de sesión).
