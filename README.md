# Agentic-RAG Audit Workflow

Interfaz de chat conversacional (Chainlit) respaldada por un backend agéntico (FastAPI) que combina RAG (Chroma) sobre documentos de auditoría con herramientas de auditoría invocables por el LLM.

**Estado:** Scaffolding base completado (deployment task 1/9). Código de aplicación en desarrollo por agentes de dominio.

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
│   ├── app.py                    # Punto de entrada (placeholder)
│   ├── config.py                 # TODO: sesión, auth
│   └── components/               # TODO: UI components
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

### 2. Levantar stack local

```bash
docker compose up --build
```

El script hace:
- Build de imágenes backend y chainlit
- Creación de volúmenes nombrados
- Inicio de servicios con healthchecks
- Espera de dependencias (chainlit espera backend healthy)

### 3. Acceder a servicios

- **UI Chainlit:** http://localhost:8001
- **Backend API:** http://localhost:8000
- **Health Check:** http://localhost:8000/api/health

### 4. Detener stack

```bash
docker compose down
```

Los volúmenes persisten entre paradas. Para limpiar completamente:
```
docker volume rm agentic-rag-audit-workflow_chroma_data agentic-rag-audit-workflow_sqlite_data agentic-rag-audit-workflow_chainlit_cache
```

---

## Plan de Desarrollo (9 Tasks)

**Task 1: Scaffolding Base** ✓ COMPLETADA (Deployment Agent)
- Estructura de carpetas, Dockerfiles, docker-compose.yml
- Endpoint health, Chainlit placeholder, pyproject.toml, docs

**Tasks 2-9:** Agentes de dominio implementan funcionalidad
- Task 2: RAG pipeline (rag-engineer)
- Task 3: Backend API core (backend-api)
- Task 4: Audit trail & findings (audit-tools)
- Task 5: Agentic loop (agentic-core)
- Task 6: Chainlit UI integration (chainlit-ui)
- Task 7: Report generation (audit-tools)
- Task 8: Tests (testing)
- Task 9: Documentation (documentation)

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

**Versión:** 0.1.0-scaffolding  
**Última actualización:** 2026-07-25  
**Próximo hito:** Task 2 (RAG Pipeline - rag-engineer)
