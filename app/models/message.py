"""ORM model for a single turn message within a `Chat` (spec-020).

Guarda DOS representaciones del mismo turno a propósito, para no tener que re-derivar una a
partir de la otra en ningún camino de lectura:

1. **Wire fidelity** (`content`, `tool_calls`, `tool_call_id`): exactamente lo que
   `app.agentic_core.loop.run_agent_turn` espera recibir de vuelta como `conversation_history`
   en el próximo turno. Para una fila `role="tool"`, `content` es el string YA envuelto en
   `<untrusted_context>` que arma `_format_search_evidence_result` (`app/agentic_core/loop.py`)
   -- se persiste tal cual, nunca reconstruido, porque perder ese wrapping al reproducir el
   historial degradaría silenciosamente la defensa de prompt-injection de spec-005.
2. **Presentación limpia** (`tool_name`, `tool_input`, `tool_output`, `report_id`): la versión
   estructurada que ya trae `ToolCallRecord` (`app/agentic_core/loop.py`), para que el frontend
   renderice un tool-step sin tener que parsear el `content` wire envuelto.

Append-only: un turno ya persistido nunca se edita ni se borra (mismo espíritu que
`Finding`/`Report`), aunque acá no hace falta `superseded_by` -- un mensaje no es una afirmación
de auditoría que se "corrija", es un renglón de transcript.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    """Una fila de transcript: `role` "user" | "assistant" | "tool"."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    chat_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chats.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    # Wire fidelity (ver docstring del módulo). `content` es None en una fila assistant que
    # solo emitió tool_calls (sin texto todavía); `tool_calls`/`tool_call_id` son None salvo en
    # las filas assistant/tool respectivamente.
    content: Mapped[str | None] = mapped_column(String, nullable=True)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Presentación limpia (ver docstring del módulo), solo en filas role="tool".
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Se completa solo si tool_name=="generate_report" y tool_output no tiene "error" (mismo
    # criterio que usaba chainlit_ui/chat.py para ofrecer la Action de aprobar/rechazar).
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
