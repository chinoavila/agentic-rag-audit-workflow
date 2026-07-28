# Estado de SDD (Spec-Driven Development)

Las specs en sí viven
únicamente en `.ai/specs/` (SSOT, ver `CLAUDE.md`) — este documento es solo el tracking de su
estado de implementación.

---

## Estado de Especificaciones (SDD)

**~119 tests** (70 passing, ~49 skipped intencionalmente — los skips corresponden a
las specs 007, 013 y 015, aún sin implementar).

| Spec | Dominio | Estado | Tests | Descripción |
|------|---------|--------|-------|-------------|
| **001** | RAG | ✅ Implementada | Pasando | Grounding y citación: respuestas incluyen referencias a chunks recuperados |
| **002** | RAG | ✅ Implementada | Pasando | Ingesta idempotente: reingestar los mismos docs no crea duplicados en índice |
| **003** | Audit Tools | ✅ Implementada | Pasando | Invocación segura de tools: errores estructurados, nunca excepción cruda hacia/desde el LLM |
| **004** | Database | ✅ Implementada | Pasando | Inmutabilidad audit trail: tabla append-only, nunca DELETE, solo soft-supersede |
| **005** | Security | ✅ Implementada | Pasando | Defensa contra prompt injection en documentos: wrapping `<untrusted_context>`, `triggered_by` (human/llm) |
| **006** | UI | ✅ Implementada | Pasando | Human-in-the-loop: aprobar/rechazar hallazgos y reportes vía `cl.Action`/endpoints explícitos |
| **007** | Backend | ❌ Pendiente | Skip | Autenticación real: actualmente stub con usuario fijo `dev-user-0` (`app/deps.py`) |
| **008** | RAG | ✅ Implementada | Pasando | Umbral de relevancia: filtro configurable en retrieval |
| **009** | Platform | ✅ Implementada | Pasando | Entorno Docker reproducible |
| **010** | Backend | ✅ Implementada | Pasando | Contrato de error uniforme: respuestas de error estructuradas |
| **011** | Audit Tools | ✅ Implementada | Pasando | Inmutabilidad de reportes generados: append-only, soft-supersede (`app/models/report.py`) |
| **012** | Audit Tools | ✅ Implementada | Pasando | Generación de informes desde plantilla + rúbricas automáticas (`app/reports/`) |
| **013** | RAG | ❌ Pendiente | Skip | Exposición dinámica de tools vía retrieval |
| **015** | Backend/Tools | ❌ Pendiente | Skip | Ejecución de comandos con permission modes de chat y ToolRun append-only |

**Resumen:**
- **Completamente implementadas:** 001, 002, 003, 004, 005, 006, 008, 009, 010, 011, 012 (11 specs)
- **Pendientes:** 007 (auth real), 013 (tool retrieval dinámico con allowlist estructural), 015 (ejecución de comandos con sandbox + permission modes) — 3 specs para próximos slices

Además del catálogo formal de arriba, el código referencia specs informales (014, 017, 018,
020) introducidas junto con la migración a frontend React — cubren el catálogo de tools,
proyectos/chats persistentes (`Chat`/`Message`/`CaseFile`/`ProjectTool`) y el sidebar de
Chainlit. No tienen todavía un spec doc SDD dedicado ni test spec propio; ver los comentarios
en código (`app/models/*`, `app/routers/*`, `chainlit_ui/chat.py`) para su alcance real.

Para el contenido completo de cada spec formal, revisar `.ai/specs/rag/`, `.ai/specs/audit/` y
`.ai/specs/platform/`.

---

## Gaps de Seguridad Conocidos y Próximos Pasos

Los siguientes gaps son conocidos, no son bugs escondidos, y están documentados en código:

| Gap | Impacto | Dueño | Próximo Paso |
|-----|---------|-------|--------------|
| **Sin allowlist de tools según contexto** | LLM puede invocar tools incluso si la instrucción vino de contenido del documento (riesgo de prompt injection). Parcialmente mitigado por diseño turn-based + prompt. | `agentic-core` + `chainlit-ui` | Implementar allowlist estructural en runtime. |
| **Sin redacción/filtrado de PII** | Contenido de chunks re-expuesto al LLM puede contener PII sin sanitizar. | `rag-engineer` o `security-compliance` | Agregar pipeline de redacción en retrieval. |
| **Auth es stub (dev-user-0 fijo)** | Sin aislamiento real de datos por usuario. Bloquea spec-007. | `backend-api` | Implementar auth real (JWT, OIDC, etc.) con aislamiento de datos. |

Estos gaps quedan para el próximo slice (specs 007 y 013).

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
- Tests pytest para specs implementadas (70 passing, 9 skipped)
- Evaluación de retrieval y contrato de herramientas

**Task 9: Documentation** ✅ COMPLETADA (documentation)
- README.md con estado verificado
- Instrucciones de setup/build/run exactas
- Tabla de estado de specs
- Documentación de gaps y próximos pasos

Desde este slice inicial ya se sumó, además, la migración a frontend React (specs informales
014/017/018/020: chats/proyectos persistentes, catálogo de tools, exportación de informes a
.docx/.pdf) corriendo en paralelo a Chainlit — ver [Arquitectura](ARCHITECTURE.md).

---

**Última actualización:** 2026-07-28
**Próximo hito:** cerrar spec-007 (auth real), spec-013 (tool retrieval dinámico con allowlist estructural)
y spec-015 (ejecución de comandos con sandbox + permission modes de chat); formalizar
las specs informales 014/017/018/020 con su spec doc SDD y test spec propios.
