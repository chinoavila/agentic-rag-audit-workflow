"""ORM model for the global tool catalog (spec-020).

Catálogo real, pero el `key` de una entry NO garantiza que exista un ejecutor de verdad:
`app/agentic_core/tools_registry.py::TOOL_DISPATCH` es la única fuente de verdad de qué tools
tienen código Python real detrás (`search_evidence`/`create_finding`/`generate_report`, las
tres seedeadas al arrancar, ver `app/main.py::_seed_tool_catalog_if_missing`). Una entry nueva
creada desde la UI (`POST /api/tools`) es deliberadamente solo METADATA -- `actions[].command`
es texto descriptivo para humanos, nunca algo que el backend ejecute. Invocar una tool sin
ejecutor registrado es, a propósito, una funcionalidad que todavía no existe (ver docstring de
`app/routers/tools.py`): agregar ejecución real de comandos arbitrarios es una superficie de
RCE que requiere su propio diseño de sandboxing/autorización, no algo para improvisar acá.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ToolCatalogEntry(Base):
    __tablename__ = "tool_catalog_entries"

    # `key` (no un uuid) es el identificador de negocio -- coincide con el nombre real de la
    # tool en `TOOL_DISPATCH` cuando existe ejecutor, o es un slug libre para una entry
    # metadata-only.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    installed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # [{"id": str, "label": str, "command": str}, ...] -- ver docstring del módulo.
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
