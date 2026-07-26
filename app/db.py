"""
SQLAlchemy engine/session setup for the audit trail persistence layer.

Lee `AUDIT_DATABASE_URL` de variables de entorno (en Docker: `sqlite:////data/audit_trail.db`,
montado sobre el volumen nombrado `sqlite_data`). Fuera de Docker (dev local) cae en un
archivo sqlite relativo al cwd del proceso.

Deliberadamente NO se llama `DATABASE_URL`: Chainlit trata la sola presencia de esa variable
de entorno como señal para inicializar su propio data layer de persistencia (threads/mensajes)
respaldado por Postgres (`chainlit.data.get_data_layer`), y crashea el endpoint
`/project/settings` con `ModuleNotFoundError: asyncpg` si no es una URL de Postgres válida
— rompiendo el arranque de la SPA de Chainlit (pantalla en blanco) aunque nunca se pidió ese
data layer. Usar un nombre de variable propio evita la colisión.

Nunca abrir una sesión manual dentro de un endpoint: usar siempre `Depends(get_db)`
(ver `.ai/skills/fastapi/SKILL.md` regla de sesión de DB).
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("AUDIT_DATABASE_URL", "sqlite:///./dev_audit_trail.db")

# `check_same_thread=False` es necesario para SQLite cuando la app sirve requests
# concurrentes desde distintos threads del pool de uvicorn/FastAPI.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa compartida por todos los modelos ORM de la app."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI que entrega una sesión de DB por request y la cierra al final.

    Uso: `db: Session = Depends(get_db)`. Nunca instanciar `SessionLocal()` a mano
    dentro de un endpoint.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
