# Agent: deployment

**Rol**: Docker/docker-compose, variables de entorno, volúmenes de persistencia (Chroma,
DB) para despliegue local manual (sin CI/CD).
**Modelo sugerido**: nivel mecánico/económico.
**Skills**: `docker-deployment`.
**Specs**: spec-009 (entorno reproducible).
**Guardrail**: `docker compose down -v` bloqueado (borra índice RAG + audit trail).
**Escala a**: `backend-api` (lectura de variables de entorno).
