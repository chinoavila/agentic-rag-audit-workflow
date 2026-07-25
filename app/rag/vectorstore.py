"""Acceso compartido al vector store (Chroma) para ingestion.py y retrieval.py.

Centraliza acá el nombre de colección, el modelo de embeddings y la ruta de
persistencia para que ingesta y retrieval nunca puedan divergir y terminar
apuntando a colecciones/modelos distintos (`.ai/skills/rag-ingestion/SKILL.md`
regla 5, `.ai/skills/vectorstore-chroma-faiss/SKILL.md` regla 3).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import chromadb
from chromadb.utils import embedding_functions

if TYPE_CHECKING:  # pragma: no cover - solo para type hints, no se ejecuta en runtime.
    # El path exacto de estos tipos internos varía entre versiones de chromadb; se
    # importan solo bajo TYPE_CHECKING (combinado con `from __future__ import
    # annotations`) para no arriesgar un ImportError en runtime por un cambio de
    # path interno entre versiones de `chromadb` (`pyproject.toml` fija solo un
    # piso `chromadb>=0.4.0`, sin techo).
    from chromadb import ClientAPI
    from chromadb.api.models.Collection import Collection

# Modelo de embeddings explícito (rag-ingestion SKILL.md regla 5: "no implícito").
# `all-MiniLM-L6-v2` es el modelo local por defecto que trae
# `chromadb.utils.embedding_functions.DefaultEmbeddingFunction()` (sentence-transformers,
# corre vía onnxruntime, sin llamadas externas). Se instancia acá explícitamente en vez
# de dejar que Chroma use un default implícito si no se pasa `embedding_function`.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_FUNCTION = embedding_functions.DefaultEmbeddingFunction()

# Naming de colección explícito y versionado: {dominio}_{modelo_embedding}_v{n}
# (vectorstore-chroma-faiss SKILL.md regla 2). Bump a v2 si cambia el modelo de
# embeddings (regla 3 de la misma skill: nunca mezclar dimensiones en una colección).
COLLECTION_NAME = f"audit_docs_{EMBEDDING_MODEL_NAME}_v1"

# Persistencia en volumen Docker dedicado, nunca en un path efímero
# (vectorstore-chroma-faiss SKILL.md regla 1). En docker-compose.yml el volumen
# nombrado `chroma_data` se monta en `/data/chroma` y `CHROMA_PERSIST_DIR` lo
# apunta ahí; ese mismo env var se respeta acá. El fallback es solo para
# ejecución local fuera de Docker (tests, scripts manuales) y debe seguir
# siendo un directorio persistente real, no `/tmp`.
DEFAULT_CHROMA_PERSIST_DIR = "/data/chroma"


def get_persist_dir() -> str:
    return os.environ.get("CHROMA_PERSIST_DIR", DEFAULT_CHROMA_PERSIST_DIR)


def get_chroma_client() -> ClientAPI:
    """Cliente Chroma persistente. Nunca `chromadb.EphemeralClient()` fuera de tests."""
    return chromadb.PersistentClient(path=get_persist_dir())


def get_collection(client: ClientAPI | None = None) -> Collection:
    """Obtiene (o crea) la colección versionada de documentos de auditoría.

    `hnsw:space: cosine` se fija explícitamente para que las `distances` que
    devuelve `collection.query(...)` sean distancia coseno (1 - similitud
    coseno); `app/rag/retrieval.py` depende de esa convención para calcular
    `similarity` y compararla contra `SIMILARITY_THRESHOLD`.
    """
    client = client or get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
        metadata={
            "embedding_model": EMBEDDING_MODEL_NAME,
            "domain": "audit_docs",
            "hnsw:space": "cosine",
        },
    )
