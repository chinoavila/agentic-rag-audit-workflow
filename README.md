# Agentic-RAG Audit Workflow

Interfaz de chat conversacional (Chainlit) respaldada por un backend agéntico (FastAPI) que combina RAG (Chroma) sobre documentos de auditoría con herramientas de auditoría invocables por el LLM.

**Estado:** Primer slice end-to-end completado (tasks 1-8 finalizadas, 9 en progreso). Build verificado, stack funcional en Docker, 46 tests pasando.

---

## Stack

- **UI conversacional**: Chainlit (puerto 8001)
- **Backend API**: FastAPI + Uvicorn (puerto 8000)
- **LLM**: Groq API (vía cliente OpenAI compatible)
- **Vector Store**: Chroma (persistencia a disco en volumen Docker)
- **Database**: SQLite (audit trail immutable, persistencia en volumen Docker)
- **Orquestación**: Tool-calling/function-calling sobre el LLM

---

## Estructura de Carpetas

```
.
├── app/                           # Backend FastAPI (agent: backend-api)
│   ├── main.py                   # Punto de entrada (health endpoint `/api/health`)
│   ├── routers/                  # Endpoints por responsabilidad
│   ├── models/                   # SQLAlchemy ORM
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── rag/                      # Pipeline de RAG (Chroma)
│   └── tools/                    # Audit tools para LLM
├── chainlit_ui/                  # UI conversacional
│   ├── chat.py                   # Punto de entrada (Chainlit loader inserta este directorio al inicio de sys.path; no llamar app.py para evitar colisión con paquete top-level)
│   ├── config.py                 # Sesión, auth
│   └── components/               # UI components
├── docs/sample_evidence/         # Documentos de auditoría de ejemplo
├── tests/                        # Pytest tests
├── Dockerfile.backend            # Backend service image
├── Dockerfile.chainlit           # Chainlit UI service image
├── docker-compose.yml            # Orquestación de servicios
├── pyproject.toml                # Declaración de dependencias
└── .env.example                  # Template de variables de entorno
```

---

## Decisiones de Arquitectura

### Volúmenes Docker Nombrados (Spec-009)

Para garantizar reproducibilidad y persistencia:

| Volumen | Ruta | Propósito |
|---------|------|----------|
| `chroma_data` | `/data/chroma` | Índice Chroma (RAG) |
| `sqlite_data` | `/data` | Base de datos SQLite (audit trail) |
| `chainlit_cache` | `/app/.chainlit` | Cache de sesiones |

**Guardrail:** Nunca eliminar volúmenes en scripts automatizados. Los datos persisten entre `docker compose up/down`.

### Servicios Separados

- **backend** (FastAPI): puerto 8000, responsabilidad API y persistencia
- **chainlit** (Chainlit): puerto 8001, responsabilidad UI conversacional
- Network `audit-network` para comunicación entre servicios

### Variables de Entorno

Todas las variables sensibles se leen desde archivo `.env` (no versionado):
- `GROQ_API_KEY`: Token para LLM Groq (requerido)
- `BACKEND_API_URL`: URL de acceso al backend desde Chainlit
- `CHROMA_PERSIST_DIR`: Ruta de persistencia Chroma
- `DATABASE_URL`: Cadena de conexión SQLite

Ver `.env.example` para template completo. El archivo `.env.example` está versionado en git para referencia; los valores reales van solo en `.env` (en gitignore).

---

## Quickstart

### 1. Preparar ambiente

```bash
git clone <repo>
cd agentic-rag-audit-workflow
cp .env.example .env
# Editar .env y rellenar GROQ_API_KEY con valor real de https://console.groq.com
```

### 2. Build e inicio del stack

```bash
# Build de imágenes (primera vez o después de cambios en Dockerfile/dependencies)
docker compose build

# Iniciar servicios en background
docker compose up -d
```

### 3. Verificar salud de servicios

```bash
# Health check del backend
curl http://localhost:8000/api/health

# Ingesta de documentos de auditoría de ejemplo (docs/sample_evidence/)
curl -X POST http://localhost:8000/api/rag/ingest

# Acceder a UI Chainlit
# Navegador: http://localhost:8001
```

### 4. Ejecutar tests

Todos los tests se ejecutan dentro del contenedor (el host no tiene las dependencias Python instaladas):

```bash
# Tests de specs implementadas en este slice (46 passing, 1 skipped intencional)
docker compose run --rm backend python -m pytest -m "spec_001 or spec_002 or spec_004 or spec_005 or spec_008 or spec_010"
```

### 5. Detener stack

```bash
docker compose down
```

Los volúmenes persisten entre paradas. Para limpiar completamente (borra índice Chroma, audit trail, sesiones):
```bash
docker volume rm agentic-rag-audit-workflow_chroma_data agentic-rag-audit-workflow_sqlite_data agentic-rag-audit-workflow_chainlit_cache
```

**Advertencia:** La eliminación de volúmenes borra toda la historia de auditoría y el índice RAG. Solo hacer para reset total.

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

Para detalles, revisar `.ai/specs/rag/`, `.ai/specs/audit/` y `.ai/specs/platform/`.

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

## Guardrails Críticos

Restricciones que deben respetarse:
- Nunca eliminar volúmenes en scripts (evita perder índice RAG y audit trail)
- Nunca hardcodear secrets en docker-compose.yml (siempre via .env)
- Nunca ejecutar instalación de paquetes en host (usar docker compose exec en contenedor)
- Nunca DELETE/UPDATE directo en tablas de auditoría (usar soft-supersede con campo superseded_by)

---

## Para los Agentes de Dominio

### Convenciones de Estructura

- **Routers**: `app/routers/` separados por responsabilidad (audit_cases.py, rag_retrieval.py, tools.py)
- **Modelos**: `app/models/` para ORM SQLAlchemy (audit_case, audit_trail, findings, report)
- **Schemas**: `app/schemas/` para validación Pydantic
- **RAG Pipeline**: `app/rag/` (chroma_client, ingestion, retrieval, reranking)
- **Tools**: `app/tools/` (function-calling para LLM invocables)

### Comunicación Entre Agentes

Si necesitas cambiar:
- **Variables de entorno**: actualizar `.env.example` + comunicar en resumen
- **Puertos/Servicios**: comunicar cambios (backend=8000, chainlit=8001 por defecto)
- **Volúmenes/Paths**: verificar que docker-compose.yml sigue consistente
- **Dependencias Python**: agregar a `pyproject.toml` + ejecutar `docker compose up --build`

---

## Referencias

- Specs: `.ai/specs/rag/`, `.ai/specs/audit/`, `.ai/specs/platform/`
- Skills: `.ai/skills/docker-deployment/`, `.ai/skills/vectorstore-chroma-faiss/`
- Guardrails: `.ai/guardrails/restricted-ops.json`
- Agentes: `.claude/agents/` (ver especificaciones de cada dominio)

---

**Versión:** 0.1.0-e2e-slice-1  
**Última actualización:** 2026-07-25  
**Próximo hito:** Slice 2 (Specs 007, 011, 012, 013 — Auth real, reportes generados, tool retrieval dinámico)
