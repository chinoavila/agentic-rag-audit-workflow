"""
FastAPI backend for Agentic-RAG Audit Workflow.

Servicios:
- /api/health: Health check endpoint
- /api/audit/: Audit case management (placeholder)
- /api/rag/: RAG retrieval endpoints (placeholder)
- /api/tools/: Audit tools invocation (placeholder)
"""

import os

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db import Base, engine
from app.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.routers import (
    audit_cases,
    case_files,
    chats,
    findings,
    project_tools,
    rag_retrieval,
    reports,
    tools,
)

# Aseguramos que los modelos ORM estén importados (y por lo tanto registrados en
# `Base.metadata`) antes de crear las tablas en el startup event de abajo.
from app import models  # noqa: F401  (import necesario para el side-effect de registro)

# Create FastAPI application
app = FastAPI(
    title="Agentic-RAG Audit Workflow Backend",
    description="Backend para orquestación de auditoría agéntica con RAG",
    version="0.1.0",
)

# Frontend React (spec-020): un SPA en un origen distinto (Vite dev server, :5173 por default)
# necesita CORS explícito para llamar esta API. `allow_credentials=False` es deliberado: no hay
# auth real todavía (`app/deps.py::get_current_user` es un stub fijo) así que no hay
# cookies/sesión que proteger -- revisar cuando `security-compliance` implemente auth real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Contrato de error uniforme (spec-010): toda excepción responde {"detail": ..., "code": ...}
# con un status code del set documentado (200, 201, 400, 401, 403, 404, 422, 500).
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(audit_cases.router)
app.include_router(case_files.router)
app.include_router(chats.router)
app.include_router(findings.router)
app.include_router(project_tools.router)
app.include_router(rag_retrieval.router)
app.include_router(reports.router)
app.include_router(tools.router)


@app.on_event("startup")
def _create_tables_if_missing() -> None:
    """Crea las tablas del audit trail si no existen todavía.

    Prototipo sin herramienta de migraciones (no hay Alembic configurado aún): esto es
    idempotente vía `checkfirst=True` (default de `create_all`) y seguro de correr en cada
    arranque del contenedor `backend`, incluso contra el volumen `sqlite_data` persistente.
    """
    Base.metadata.create_all(bind=engine)
    _migrate_add_triggered_by_if_missing()
    _migrate_add_context_if_missing()
    _seed_tool_catalog_if_missing()


def _migrate_add_triggered_by_if_missing() -> None:
    """Migración puntual: agrega `findings.triggered_by` si la tabla ya existía de una
    sesión anterior al agregado de esta columna (volumen `sqlite_data` persistente).

    `create_all()` de arriba NO altera tablas ya existentes, así que sin esto cualquier
    query sobre `findings` contra un volumen viejo rompe con "no such column:
    findings.triggered_by" — borrar ese volumen para forzar una recreación no es la
    respuesta correcta acá: el audit trail es append-only por diseño (spec-004), no algo
    para tirar y recrear por un cambio de schema.

    Esto NO es un motor de migraciones genérico, es un parche puntual y documentado. Si el
    modelo vuelve a cambiar de forma incompatible con datos existentes, hace falta un
    mecanismo real (Alembic) en vez de seguir apilando parches acá.
    """
    inspector = inspect(engine)
    if not inspector.has_table("findings"):
        return
    existing_columns = {col["name"] for col in inspector.get_columns("findings")}
    if "triggered_by" in existing_columns:
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE findings ADD COLUMN triggered_by VARCHAR(16) NOT NULL DEFAULT 'human'")
        )
        conn.commit()


def _migrate_add_context_if_missing() -> None:
    """Migración puntual: agrega `audit_cases.context` (spec-020, frontend React) si la tabla
    ya existía de una sesión anterior a este agregado. Mismo patrón que
    `_migrate_add_triggered_by_if_missing` -- ver ese docstring.
    """
    inspector = inspect(engine)
    if not inspector.has_table("audit_cases"):
        return
    existing_columns = {col["name"] for col in inspector.get_columns("audit_cases")}
    if "context" in existing_columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE audit_cases ADD COLUMN context TEXT"))
        conn.commit()


_SEED_TOOL_CATALOG: list[dict] = [
    {
        "key": "search_evidence",
        "label": "Buscar evidencia",
        "description": "Busca evidencia relevante en los documentos indexados (RAG) y devuelve citas con página y similitud.",
        "kind": "ro",
        "actions": [{"id": "act_search", "label": "Buscar evidencia", "command": "internal:search_evidence"}],
    },
    {
        "key": "create_finding",
        "label": "Registrar hallazgo",
        "description": "Registra un hallazgo de auditoría con severidad, evidencia citada y risk score.",
        "kind": "write",
        "actions": [{"id": "act_create_finding", "label": "Crear hallazgo", "command": "internal:create_finding"}],
    },
    {
        "key": "generate_report",
        "label": "Generar informe",
        "description": "Genera un informe desde una plantilla y corre las rúbricas automáticas antes de persistir.",
        "kind": "write",
        "actions": [{"id": "act_generate_report", "label": "Generar borrador desde plantilla", "command": "internal:generate_report"}],
    },
]


def _seed_tool_catalog_if_missing() -> None:
    """Puebla `tool_catalog_entries` con las 3 tools que YA tienen ejecutor real en
    `TOOL_DISPATCH` (`app/agentic_core/tools_registry.py`), una sola vez -- si la tabla ya
    tiene filas (p. ej. porque un humano agregó una tool custom desde la UI), no toca nada.
    `command="internal:<nombre>"` es solo una convención legible para humanos en este seed;
    el backend nunca la parsea ni la ejecuta -- lo que decide si una tool corre de verdad es
    si su `key` está en `TOOL_DISPATCH`, no el texto de `command` (ver
    `app/models/tool_catalog_entry.py`).
    """
    from app.models.tool_catalog_entry import ToolCatalogEntry
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        if db.query(ToolCatalogEntry).count() > 0:
            return
        for entry in _SEED_TOOL_CATALOG:
            db.add(ToolCatalogEntry(installed=True, **entry))
        db.commit()
    finally:
        db.close()


@app.get("/api/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.

    Verificación de que el backend está activo y accesible.
    Los siguientes agentes integrarán chequeos adicionales:
    - Conectividad a Chroma (RAG)
    - Conectividad a SQLite (audit trail)
    - Conectividad a Groq (LLM)
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "audit-workflow-backend",
            "version": "0.1.0",
        },
    )


# ============================================================================
# Registrados arriba:
# - app/routers/audit_cases.py  -> /api/audit-cases (backend-api agent)
# - app/routers/findings.py     -> /api/findings     (backend-api agent)
# - app/routers/rag_retrieval.py -> /api/rag/query, /api/rag/ingest (rag-engineer agent)
#
# Pendiente de otro agente en paralelo:
# - app/routers/tools.py (audit-tools agent)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
