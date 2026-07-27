"""ORM model for a conversation thread (spec-020, frontend React migration).

Reemplaza el rol que tenía `cl.user_session["conversation_history"]` en la UI de Chainlit: un
frontend SPA sin estado necesita recargar el historial real desde la base antes de cada turno
(ver `app/routers/chats.py::post_chat_message`), así que un `Chat` (y sus `Message`, ver
`app/models/message.py`) deja de ser "nice to have" y pasa a ser infraestructura obligatoria.

Un proyecto (`AuditCase`) contiene múltiples chats independientes (`case_id` no nulo); también
existen chats standalone sin proyecto (`case_id` nulo) -- mismo modelo para ambos casos, sin una
tabla separada.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chat(Base):
    """Un hilo de conversación. `title` se autocompleta con el primer mensaje si queda `None`."""

    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("audit_cases.id"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # Se actualiza en cada mensaje nuevo (ver post_chat_message) para poder ordenar el nav por
    # actividad reciente sin tener que hacer un join/agregado contra `messages` en cada listado.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
