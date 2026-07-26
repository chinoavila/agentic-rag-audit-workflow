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
from chromadb.api.types import Documents, Embeddings
from chromadb.api.types import EmbeddingFunction as ChromaEmbeddingFunction

if TYPE_CHECKING:  # pragma: no cover - solo para type hints, no se ejecuta en runtime.
    # El path exacto de estos tipos internos varía entre versiones de chromadb; se
    # importan solo bajo TYPE_CHECKING (combinado con `from __future__ import
    # annotations`) para no arriesgar un ImportError en runtime por un cambio de
    # path interno entre versiones de `chromadb` (`pyproject.toml` fija solo un
    # piso `chromadb>=0.4.0`, sin techo).
    from chromadb import ClientAPI
    from chromadb.api.models.Collection import Collection

# Modelo de embeddings explícito (rag-ingestion SKILL.md regla 5: "no implícito").
# NO usamos `DefaultEmbeddingFunction()` (all-MiniLM-L6-v2): es un modelo optimizado
# para inglés que en la práctica no discrimina bien contenido en español — para el
# corpus real de `docs/references/` (normativa de auditoría en español) devolvía
# resultados genéricos/parejos (~0.65-0.74 de similitud sin importar relevancia real)
# y no lograba priorizar el pasaje correcto de entre las top-30 respuestas para una
# consulta cuyo texto literal SÍ está en el corpus.
#
# `paraphrase-multilingual-MiniLM-L12-v2` está entrenado explícitamente para +50
# idiomas (incluido español) y da resultados sensiblemente mejores para este corpus.
# Se sirve vía la librería `fastembed` de Qdrant (ONNX Runtime puro) en vez de
# `SentenceTransformerEmbeddingFunction` (que arrastra pytorch/transformers
# completos, varios GB) — mismo modelo, mismos vectores, ~220MB de descarga en
# vez de un stack de ML pesado innecesario para inferencia.
#
# La versión de chromadb fijada acá (1.5.9) ya no expone un `FastEmbedEmbeddingFunction`
# de fábrica en `chromadb.utils.embedding_functions` (solo quedó la variante sparse),
# así que se envuelve `fastembed.TextEmbedding` a mano implementando el protocolo
# `EmbeddingFunction` de chromadb (`__call__(Documents) -> Embeddings` es lo único
# que exige en runtime; `name`/`get_config`/`build_from_config` tienen default no
# implementado en la clase base y no hacen falta porque acá siempre se pasa la
# instancia ya construida, nunca se reconstruye desde config serializada).


class _FastEmbedMultilingualFunction(ChromaEmbeddingFunction[Documents]):
    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def __call__(self, input: Documents) -> Embeddings:
        return [vector.tolist() for vector in self._model.embed(list(input))]

    def name(self) -> str:
        return "fastembed-multilingual"


EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_FUNCTION = _FastEmbedMultilingualFunction(
    model_name=f"sentence-transformers/{EMBEDDING_MODEL_NAME}"
)

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
