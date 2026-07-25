"""Pipeline de ingesta: load -> validate -> chunk -> embed -> upsert(chroma).

Idempotencia (spec-002, `.ai/skills/rag-ingestion/SKILL.md` regla 2): antes de
indexar se calcula `doc_hash = sha256(contenido)` y se compara contra el/los
`doc_hash` ya indexados con el mismo `source`:
  - mismo hash -> se hace skip (no se re-embebe ni se duplica nada).
  - hash distinto -> se borran los chunks viejos de ese `source` y se insertan
    los nuevos (replace, nunca acumular).
  - sin chunks previos -> insert normal.

El `id` de cada chunk en Chroma es `f"{doc_hash}_{section}"`, lo que da además
dedup a nivel de vector store (`.ai/skills/vectorstore-chroma-faiss/SKILL.md`
regla 4): reinsertar el mismo chunk (mismo hash+sección) es un upsert sobre el
mismo id, nunca una fila nueva.

SEGURIDAD (spec-005, `.ai/skills/security-prompt-injection/SKILL.md`): el
contenido de los documentos ingeridos es DATO. Este módulo no interpreta, ni
ejecuta, ni concatena ese texto a ningún prompt — solo lo trocea y lo indexa.
Si al ingestar aparece contenido que luce como una instrucción dirigida al LLM
("ignorá las instrucciones anteriores y...", etc.), la política del proyecto
es escalar a `security-compliance` (ver `.ai/handoffs/escalation-map.md`) antes
de indexarlo; este módulo no intenta detectarlo automáticamente en este slice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.rag.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text
from app.rag.vectorstore import get_collection

if TYPE_CHECKING:  # pragma: no cover - solo type hints, ver app/rag/vectorstore.py
    from chromadb.api.models.Collection import Collection

# Validación explícita de extensión/mimetype antes de procesar
# (rag-ingestion SKILL.md regla 6): para este slice solo se acepta texto plano
# y markdown. Cualquier otro formato se rechaza con un error claro en vez de
# intentar parsearlo como texto.
SUPPORTED_EXTENSIONS = {".md", ".txt"}


class UnsupportedFormatError(ValueError):
    """El archivo no tiene una extensión/mimetype soportado por la ingesta."""


@dataclass(frozen=True)
class IngestionResult:
    """Resultado de ingerir un único documento."""

    source: str
    doc_hash: str
    status: str  # "inserted" | "replaced" | "skipped_unchanged"
    chunks_indexed: int


def compute_doc_hash(content: str) -> str:
    """sha256 del contenido completo del archivo (spec-002)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_supported_format(file_path: Path) -> None:
    """Levanta `UnsupportedFormatError` si la extensión no está soportada."""
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Formato no soportado: '{file_path.name}' (extensión '{file_path.suffix}'). "
            f"Este slice solo acepta {sorted(SUPPORTED_EXTENSIONS)}."
        )


def load_document(file_path: Path) -> str:
    """load + validate: valida extensión, lee el archivo y valida que sea texto UTF-8.

    Rechaza explícitamente binarios que pasaron el filtro de extensión (defensa
    en profundidad además del chequeo de extensión).
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {file_path}")

    validate_supported_format(file_path)

    raw_bytes = file_path.read_bytes()
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            f"'{file_path.name}' tiene extensión soportada pero el contenido no es "
            f"texto UTF-8 válido (posible binario)."
        ) from exc


def ingest_document(file_path: Path, collection: Collection | None = None) -> IngestionResult:
    """Ingesta idempotente de un único documento (load -> validate -> chunk -> embed -> upsert)."""
    collection = collection or get_collection()

    text = load_document(file_path)
    doc_hash = compute_doc_hash(text)
    source = file_path.name

    existing = collection.get(where={"source": source})
    existing_ids: list[str] = existing.get("ids", []) or []
    existing_metadatas = existing.get("metadatas", []) or []
    existing_hashes = {meta["doc_hash"] for meta in existing_metadatas if meta}

    # Idempotencia (spec-002): mismo doc_hash ya indexado -> skip, no duplicar.
    if existing_ids and existing_hashes == {doc_hash}:
        return IngestionResult(
            source=source, doc_hash=doc_hash, status="skipped_unchanged", chunks_indexed=0
        )

    is_replace = bool(existing_ids)
    if existing_ids:
        # Documento cambió (hash distinto) -> reemplazar chunks viejos, no acumular.
        collection.delete(ids=existing_ids)

    chunks = chunk_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError(f"'{source}' no produjo chunks (contenido vacío tras normalizar).")

    ingested_at = datetime.now(timezone.utc).isoformat()
    ids = [f"{doc_hash}_{chunk.section}" for chunk in chunks]
    documents = [chunk.text for chunk in chunks]
    # Metadata obligatoria por chunk (rag-ingestion SKILL.md regla 1):
    # source, page, doc_hash, ingested_at.
    metadatas = [
        {
            "source": source,
            "page": chunk.section,
            "doc_hash": doc_hash,
            "ingested_at": ingested_at,
        }
        for chunk in chunks
    ]

    # embed + upsert: Chroma embebe con el embedding_function de la colección
    # (ver app/rag/vectorstore.py) al llamar upsert/add. `upsert` (no `add`) es
    # lo que hace que reingerir el mismo id sea seguro en vez de lanzar error.
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return IngestionResult(
        source=source,
        doc_hash=doc_hash,
        status="replaced" if is_replace else "inserted",
        chunks_indexed=len(chunks),
    )


def ingest_directory(
    directory: Path, collection: Collection | None = None
) -> list[IngestionResult]:
    """Ingesta todos los archivos de `directory` (no recursivo), en orden alfabético.

    Falla explícitamente (propaga `UnsupportedFormatError`) si algún archivo no
    tiene un formato soportado, en vez de saltearlo en silencio (spec-002:
    "ingerir un archivo con formato no soportado falla explícitamente").
    """
    collection = collection or get_collection()
    results = []
    for file_path in sorted(p for p in directory.iterdir() if p.is_file()):
        results.append(ingest_document(file_path, collection=collection))
    return results
