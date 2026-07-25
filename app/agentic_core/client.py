"""Cliente Groq/OpenAI-compatible usado por el loop agéntico (`app/agentic_core/loop.py`).

Decisión de runtime (task 1, `deployment`): el LLM corre en Groq, accedido vía el cliente
Python `openai` apuntando a la API compatible con OpenAI que expone Groq
(`base_url="https://api.groq.com/openai/v1"`), leyendo `GROQ_API_KEY` de env (nunca
hardcodeada, ver `docker-compose.yml`/`.env.example`).

Decisión de modelo — `MODEL_NAME = "llama-3.3-70b-versatile"`:
Es, dentro del catálogo de Groq, el modelo con mejor soporte de tool-calling/function-calling
disponible para este slice: sigue de forma confiable el schema JSON declarado en
`tools=[...]` (`app/agentic_core/tools_registry.py`) y decide correctamente cuándo invocar
`search_evidence` vs `create_finding` vs responder directo, algo que las variantes
`*-8b-instant` priorizan sacrificar (más rápidas/baratas, pero menos consistentes armando
argumentos de tool-calls válidos). Si en el futuro Groq deprecara este modelo o se necesitara
más velocidad a costa de precisión en tool-calling, este es el único símbolo a cambiar — todo
lo demás (`loop.py`, `tools_registry.py`) es agnóstico del modelo concreto.

Se usa `openai.AsyncOpenAI` (no el cliente sync) porque `run_agent_turn` es async de punta a
punta, pensado para no bloquear el event loop de FastAPI/Chainlit mientras se espera la
respuesta del LLM.
"""

from __future__ import annotations

import os

from openai import AsyncOpenAI

# API compatible con OpenAI que expone Groq (chat completions + tool-calling).
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

MODEL_NAME = "llama-3.3-70b-versatile"

# Lazy singleton: no se instancia al importar el módulo (para no romper import-time en tests
# que no seteen `GROQ_API_KEY`), solo al primer uso real vía `get_client()`.
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Devuelve un `AsyncOpenAI` apuntando a Groq, leyendo `GROQ_API_KEY` de env.

    Raises:
        RuntimeError: si `GROQ_API_KEY` no está seteada en el entorno del proceso.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY no está seteada en el entorno. Ver docker-compose.yml / "
                ".env.example (deployment, task 1)."
            )
        _client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    return _client


def reset_client() -> None:
    """Resetea el singleton lazy. Uso exclusivo de tests (para inyectar env/mocks distintos)."""
    global _client
    _client = None
