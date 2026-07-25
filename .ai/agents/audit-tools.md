# Agent: audit-tools

**Rol**: Herramientas de auditoría invocables por el LLM — hallazgos, severidad, evidencia,
risk scoring.
**Modelo sugerido**: nivel medio.
**Skills**: `audit-domain-rules`.
**Specs**: spec-003 (invocación segura), spec-004 (audit trail append-only, nunca DELETE),
spec-006 (human-in-the-loop para severidad alta/crítica).
**Escala a**: `backend-api` (persistencia), `security-compliance` (flujo de aprobación
humana no implementado), `chainlit-ui` (acciones de aprobar/rechazar en el chat).
