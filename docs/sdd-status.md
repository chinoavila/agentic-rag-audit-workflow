# Estado de SDD (Spec-Driven Development)

Las specs en sí viven
únicamente en `.ai/specs/` (SSOT, ver `CLAUDE.md`) — este documento es solo el tracking de su
estado de implementación.

---

## Estado de Especificaciones (SDD)

Este primer slice implementa y valida las siguientes especificaciones:

| Spec | Dominio | Estado | Tests | Descripción |
|------|---------|--------|-------|-------------|
| **001** | RAG | ✅ Implementada | Pasando | Grounding y citación: respuestas incluyen referencias [1][2] a chunks recuperados |
| **002** | RAG | ✅ Implementada | Pasando | Ingesta idempotente: reingestar los mismos docs no crea duplicados en índice |
| **003** | Audit Tools | 🟡 Parcial | Indirecto | Invocación segura de tools: parcialmente cubierta por defensa en 005 |
| **004** | Database | ✅ Implementada | Pasando | Inmutabilidad audit trail: tabla append-only, nunca DELETE, solo soft-supersede |
| **005** | Security | 🟡 Parcial | Pasando (1 skip) | Defensa contra prompt injection en documentos: sanitización, test de `triggered_by` en skip (ver gaps) |
| **006** | UI | 🟡 Parcial | Sin test spec | Human-in-the-loop: implementado en `chainlit_ui/chat.py` vía `cl.Action` approve/reject_finding |
| **007** | Backend | ❌ Pendiente | Skip | Autenticación real: actualmente stub con usuario fijo `dev-user-0` (spec-007) |
| **008** | RAG | ✅ Implementada | Pasando | Umbral de relevancia: filtro configurable en retrieval |
| **009** | — | ❌ Pendiente | — | No implementada en este slice |
| **010** | Backend | ✅ Implementada | Pasando | Contrato de error uniforme: respuestas de error estructuradas |
| **011** | Audit Tools | ❌ Pendiente | — | Inmutabilidad de reportes generados |
| **012** | Audit Tools | ❌ Pendiente | — | Generación de informes desde plantilla |
| **013** | RAG | ❌ Pendiente | — | Exposición dinámica de tools vía retrieval |

**Resumen:**
- **Completamente implementadas:** 001, 002, 004, 008, 010 (5 specs)
- **Parcialmente implementadas:** 003, 005, 006 (3 specs — implementación presente pero sin test spec completo o con gaps conocidos)
- **Pendientes:** 007, 009, 011, 012, 013 (5 specs — para próximos slices)

Para el contenido completo de cada spec, revisar `.ai/specs/rag/`, `.ai/specs/audit/` y `.ai/specs/platform/`.

---

## Gaps de Seguridad Conocidos y Próximos Pasos

Los siguientes gaps son conocidos, no son bugs escondidos, y están documentados en código:

| Gap | Impacto | Dueño | Próximo Paso |
|-----|---------|-------|--------------|
| **Falta columna `triggered_by` en `Finding`** | Imposible rastrear si hallazgo fue creado por LLM vs. humano. Bloquea test `test_action_records_triggered_by_source` en `spec-005`. | `audit-tools` (tool) + `backend-api` (modelo/migración) | Agregar campo, migración, lógica de guardado. |
| **Sin allowlist de tools según contexto** | LLM puede invocar tools incluso si la instrucción vino de contenido del documento (riesgo de prompt injection). Parcialmente mitigado por diseño turn-based + prompt. | `agentic-core` + `chainlit-ui` | Implementar allowlist estructural en runtime. |
| **Sin redacción/filtrado de PII** | Contenido de chunks re-expuesto al LLM puede contener PII sin sanitizar. | `rag-engineer` o `security-compliance` | Agregar pipeline de redacción en retrieval. |
| **Auth es stub (dev-user-0 fijo)** | Sin aislamiento real de datos por usuario. Viola spec-007. | `backend-api` | Implementar auth real (JWT, OIDC, etc.) con aislamiento de datos. |

Todos estos gaps quedan para el próximo slice (specs 007, 011, 012, 013 y ampliación de 005-006).

---

## Plan de Desarrollo (9 Tasks)

**Task 1: Scaffolding Base** ✅ COMPLETADA (Deployment)
- Estructura de carpetas, Dockerfiles, docker-compose.yml
- Endpoint health, Chainlit placeholder, pyproject.toml, docs

**Task 2: RAG Pipeline** ✅ COMPLETADA (rag-engineer)
- Ingesta idempotente de documentos (spec-002)
- Retrieval con umbral de relevancia (spec-008)
- Grounding/citación de respuestas (spec-001)

**Task 3: Backend API** ✅ COMPLETADA (backend-api)
- Endpoints RAG, audit cases, findings
- Contrato de error uniforme (spec-010)

**Task 4: Audit Trail & Findings** ✅ COMPLETADA (audit-tools)
- Tabla append-only, soft-supersede (spec-004)
- Tools de auditoría invocables

**Task 5: Agentic Loop** ✅ COMPLETADA (agentic-core)
- Tool-calling runtime con memoria de conversación
- Defensa parcial contra prompt injection (spec-005)

**Task 6: Chainlit UI** ✅ COMPLETADA (chainlit-ui)
- Interfaz conversacional con streaming
- Human-in-the-loop para aprobación de hallazgos (spec-006)

**Task 7: Security & Compliance** ✅ COMPLETADA (security-compliance)
- Validación de prompt injection en documentos (spec-005)
- Documentación de gaps conocidos

**Task 8: Testing** ✅ COMPLETADA (testing)
- Tests pytest para specs implementadas (46 passing, 1 skipped)
- Evaluación de retrieval y contrato de herramientas

**Task 9: Documentation** 🔄 EN PROGRESO (documentation)
- README.md con estado verificado
- Instrucciones de setup/build/run exactas
- Tabla de estado de specs
- Documentación de gaps y próximos pasos

---

**Versión:** 0.1.0-e2e-slice-1
**Última actualización:** 2026-07-25
**Próximo hito:** Slice 2 (Specs 007, 011, 012, 013 — Auth real, reportes generados, tool retrieval dinámico)
