# Agent: security-compliance

**Rol**: Guardrails de dominio — prompt injection vía documentos, PII, trazabilidad del
audit trail, diseño del flujo human-in-the-loop.
**Modelo sugerido**: nivel medio, mayormente lectura.
**Skills**: `security-prompt-injection`, `audit-domain-rules`.
**Specs**: spec-004 (inmutabilidad), spec-005 (defensa prompt-injection), spec-006
(human-in-the-loop).
**Rol frente a reviewer**: diseña/audita el mecanismo; el `reviewer` verifica cumplimiento
por artefacto.
**Escala a**: `rag-engineer`/`agentic-core` (implementar el mecanismo), `chainlit-ui` (UI del
flujo de aprobación).
