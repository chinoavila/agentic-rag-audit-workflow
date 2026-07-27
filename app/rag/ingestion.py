"""Pipeline de ingesta: load -> validate -> chunk -> embed -> upsert(chroma).

Idempotencia (spec-002, `.ai/skills/rag-ingestion/SKILL.md` regla 2): antes de
indexar se calcula `doc_hash = sha256(contenido)` y se compara contra el/los
`doc_hash` ya indexados con el mismo `source`:
  - mismo hash -> se hace skip (no se re-embebe ni se duplica nada).
  - hash distinto -> se borran los chunks viejos de ese `source` y se insertan
    los nuevos (replace, nunca acumular).
  - sin chunks previos -> insert normal.

El `id` de cada chunk en Chroma es `f"{doc_hash}_{section}"` (`.md`/`.txt`) o
`f"{doc_hash}_{global_index}"` (formatos binarios, `global_index` = índice
secuencial de chunk a través de todo el documento, incluso cuando varios
chunks comparten el mismo `page` real de PDF), lo que da además dedup a nivel
de vector store (`.ai/skills/vectorstore-chroma-faiss/SKILL.md` regla 4):
reinsertar el mismo chunk (mismo hash+índice) es un upsert sobre el mismo id,
nunca una fila nueva.

SEGURIDAD (spec-005, `.ai/skills/security-prompt-injection/SKILL.md`): el
contenido de los documentos ingeridos es DATO. Este módulo no interpreta, ni
ejecuta, ni concatena ese texto a ningún prompt — solo lo trocea y lo indexa.
Si al ingestar aparece contenido que luce como una instrucción dirigida al LLM
("ignorá las instrucciones anteriores y...", etc.), la política del proyecto
es escalar a `security-compliance` (ver `.ai/handoffs/escalation-map.md`) antes
de indexarlo; este módulo no intenta detectarlo automáticamente en este slice.

Formatos binarios (`.pdf`/`.docx`/`.xlsx`, agregados para poder indexar el
corpus real de `docs/references/`): la extracción de texto vive en
`app/rag/extractors.py`, no acá. `doc_hash` para estos formatos se calcula
sobre los BYTES CRUDOS del archivo (`compute_doc_hash(file_path.read_bytes())`)
en vez del texto decodificado — más simple y uniforme entre formatos, y no
depende de que la extracción sea perfectamente determinística entre corridas.
Para `.md`/`.txt` el hash se sigue calculando sobre el texto decodificado
(`compute_doc_hash` acepta `str | bytes` y hashea `str.encode("utf-8")`
internamente para el caso `str`), así que el valor de hash para esos dos
formatos no cambió respecto de antes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.rag.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text
from app.rag.extractors import extract_docx_text, extract_pdf_pages, extract_xlsx_text
from app.rag.vectorstore import get_collection

if TYPE_CHECKING:  # pragma: no cover - solo type hints, ver app/rag/vectorstore.py
    from chromadb.api.models.Collection import Collection

# Validación explícita de extensión/mimetype antes de procesar
# (rag-ingestion SKILL.md regla 6): formatos aceptados por la ingesta. Cualquier
# otro formato se rechaza con un error claro en vez de intentar parsearlo.
#
# `TEXT_EXTENSIONS`: decodificados directo como UTF-8 (`load_document`), sin
# pasar por `app/rag/extractors.py` — comportamiento sin cambios desde el
# slice inicial.
# `BINARY_EXTENSIONS`: requieren extracción de texto vía `app/rag/extractors.py`
# antes de poder chunkear (agregados para indexar `docs/references/`: PDF/DOCX/XLSX).
TEXT_EXTENSIONS = {".md", ".txt"}
BINARY_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | BINARY_EXTENSIONS


class UnsupportedFormatError(ValueError):
    """El archivo no tiene una extensión/mimetype soportado por la ingesta."""


@dataclass(frozen=True)
class IngestionResult:
    """Resultado de ingerir un único documento."""

    source: str
    doc_hash: str
    status: str  # "inserted" | "replaced" | "skipped_unchanged"
    chunks_indexed: int


@dataclass(frozen=True)
class IngestionFailure:
    """Fallo estructurado al ingerir un archivo dentro de un lote.

    Usado por `ingest_directory_recursive` (nunca por `ingest_directory`, que
    sigue propagando la excepción cruda — ver su docstring) para registrar,
    sin abortar el resto del lote, que un archivo puntual no se pudo ingerir
    (formato no soportado, extracción rota, PDF corrupto/encriptado, etc.).
    """

    source: str
    error_type: str
    error_message: str


def compute_doc_hash(content: str | bytes) -> str:
    """sha256 del contenido completo del archivo (spec-002).

    Acepta texto ya decodificado (`.md`/`.txt`, comportamiento original: se
    hashea `content.encode("utf-8")`, mismo resultado que antes) o bytes crudos
    (formatos binarios `.pdf`/`.docx`/`.xlsx`: se hashea el archivo tal cual,
    sin depender de que la extracción de texto sea determinística).
    """
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


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


def _resolve_source(file_path: Path, base_dir: Path | None) -> str:
    """`source` default (`file_path.name`) o path relativo a `base_dir` si se pasa.

    `base_dir` es lo que usa `ingest_directory_recursive` para dar un `source`
    sin colisiones entre archivos del mismo nombre en subcarpetas distintas
    (ej. `"Estandares/1001_std.pdf"` en vez de solo `"1001_std.pdf"`), con
    separadores `/` (`Path.as_posix()`) para que la cita sea legible y estable
    entre plataformas.
    """
    if base_dir is None:
        return file_path.name
    return file_path.resolve().relative_to(base_dir.resolve()).as_posix()


def _extract_units(file_path: Path, suffix: str) -> list[tuple[int | None, str]]:
    """Extrae el texto de un archivo binario como `[(page_o_None, texto), ...]`.

    - `.pdf`: una unidad por página, con el número de página PDF REAL (1-based).
      Varios chunks pueden terminar compartiendo el mismo número de página — eso
      es correcto, significa que esos chunks vinieron de la misma página.
    - `.docx` / `.xlsx`: una única unidad con `page=None`; `ingest_document`
      interpreta `page=None` como "no hay página real, usar el índice
      secuencial de chunk" — misma convención que `.md`/`.txt`
      (`app/rag/chunking.py`).

    Raises:
        UnsupportedFormatError: si `suffix` no es un formato binario conocido
            (no debería ocurrir si se llama después de `validate_supported_format`).
        ExtractionError: ver `app/rag/extractors.py` (PDF corrupto/encriptado,
            DOCX/XLSX corrupto, librería de extracción no instalada).
    """
    if suffix == ".pdf":
        return [(page_num, text) for page_num, text in extract_pdf_pages(file_path)]
    if suffix == ".docx":
        return [(None, extract_docx_text(file_path))]
    if suffix == ".xlsx":
        return [(None, extract_xlsx_text(file_path))]
    raise UnsupportedFormatError(  # pragma: no cover - defensa en profundidad, no alcanzable en uso normal
        f"'{file_path.name}': extensión '{suffix}' no tiene extractor binario registrado."
    )


def ingest_document(
    file_path: Path,
    collection: Collection | None = None,
    *,
    base_dir: Path | None = None,
    case_id: str = "global",
) -> IngestionResult:
    """Ingesta idempotente de un único documento (load -> validate -> chunk -> embed -> upsert).

    `base_dir`: opcional. Si se pasa, `source` es el path de `file_path` RELATIVO
    a `base_dir` (ver `_resolve_source`) en vez de solo `file_path.name` — lo usa
    `ingest_directory_recursive` para corpus con subcarpetas (`docs/references/`).
    Si no se pasa (default), el comportamiento es exactamente el de antes:
    `source = file_path.name`. Los call sites existentes (`ingest_directory`,
    tests) no pasan `base_dir` y no cambian de comportamiento.

    `case_id`: spec-020 (aislamiento best-effort por proyecto). `"global"` (default) es lo que
    usan `ingest_directory`/`ingest_directory_recursive` para el corpus general de
    `docs/references/`; un archivo subido a un proyecto puntual (`app/routers/case_files.py`)
    pasa el `case_id` real. `app/rag/retrieval.py::retrieve` hace una query adicional
    filtrada por este campo cuando se le pasa un `case_id`, además de la query sin filtro de
    siempre -- NO es un aislamiento estricto (el corpus `global` ingerido antes de este
    campo existir no tiene `case_id` en su metadata, así que un filtro `where` excluyente
    rompería la búsqueda general; ver docstring de `retrieve` para el detalle exacto de la
    limitación conocida).
    """
    collection = collection or get_collection()

    if not file_path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {file_path}")
    validate_supported_format(file_path)

    suffix = file_path.suffix.lower()
    source = _resolve_source(file_path, base_dir)

    if suffix in TEXT_EXTENSIONS:
        # --- Camino original para .md/.txt, sin cambios de comportamiento. ---
        text = load_document(file_path)
        doc_hash = compute_doc_hash(text)

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
                "case_id": case_id,
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

    # --- Formatos binarios: .pdf / .docx / .xlsx (docs/references/) ---
    # doc_hash sobre bytes crudos (ver docstring del módulo y de compute_doc_hash):
    # más simple/uniforme entre formatos que hashear el texto extraído.
    raw_bytes = file_path.read_bytes()
    doc_hash = compute_doc_hash(raw_bytes)

    existing = collection.get(where={"source": source})
    existing_ids = existing.get("ids", []) or []
    existing_metadatas = existing.get("metadatas", []) or []
    existing_hashes = {meta["doc_hash"] for meta in existing_metadatas if meta}

    if existing_ids and existing_hashes == {doc_hash}:
        return IngestionResult(
            source=source, doc_hash=doc_hash, status="skipped_unchanged", chunks_indexed=0
        )

    is_replace = bool(existing_ids)
    if existing_ids:
        collection.delete(ids=existing_ids)

    units = _extract_units(file_path, suffix)

    ingested_at = datetime.now(timezone.utc).isoformat()
    ids = []
    documents = []
    metadatas = []
    global_index = 0
    for unit_page, unit_text in units:
        for chunk in chunk_text(unit_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
            global_index += 1
            # PDF: page real de la unidad. .docx/.xlsx (unit_page=None): índice
            # secuencial de chunk, misma convención que .md/.txt.
            page = unit_page if unit_page is not None else global_index
            ids.append(f"{doc_hash}_{global_index}")
            documents.append(chunk.text)
            metadatas.append(
                {
                    "source": source,
                    "page": page,
                    "doc_hash": doc_hash,
                    "ingested_at": ingested_at,
                    "case_id": case_id,
                }
            )

    if not ids:
        raise ValueError(f"'{source}' no produjo chunks (contenido vacío tras extracción).")

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return IngestionResult(
        source=source,
        doc_hash=doc_hash,
        status="replaced" if is_replace else "inserted",
        chunks_indexed=len(ids),
    )


def ingest_directory(
    directory: Path, collection: Collection | None = None
) -> list[IngestionResult]:
    """Ingesta todos los archivos de `directory` (no recursivo), en orden alfabético.

    Falla explícitamente (propaga la excepción, p.ej. `UnsupportedFormatError`,
    `extractors.ExtractionError`, `ValueError`) si algún archivo no se puede
    ingerir, abortando el resto del lote, en vez de saltearlo en silencio
    (spec-002: "ingerir un archivo con formato no soportado falla
    explícitamente"). Este es el comportamiento correcto para un corpus chico y
    controlado como `docs/sample_evidence/`, donde un archivo roto es señal de
    que algo está mal y debe frenar la ingesta para que se investigue.

    Para corpus grandes y heterogéneos donde un archivo roto/no soportado NO
    debe bloquear la ingesta de los demás (`docs/references/`), usar
    `ingest_directory_recursive` en su lugar — tolera fallos parciales por
    archivo y además camina subcarpetas.
    """
    collection = collection or get_collection()
    results = []
    for file_path in sorted(p for p in directory.iterdir() if p.is_file()):
        results.append(ingest_document(file_path, collection=collection))
    return results


def ingest_directory_recursive(
    directory: Path, collection: Collection | None = None
) -> list[IngestionResult | IngestionFailure]:
    """Ingesta recursiva y tolerante a fallos parciales de `directory` (incl. subcarpetas).

    Camina `directory` recursivamente (`Path.rglob("*")`, filtrando solo
    archivos) y por CADA archivo intenta
    `ingest_document(file_path, collection=collection, base_dir=directory)` —
    pasar `base_dir=directory` hace que `source` sea el path relativo a
    `directory` (ej. `"Estandares/1001_std.pdf"`), evitando colisiones entre
    archivos del mismo nombre en subcarpetas distintas y dando una cita legible.

    Diferencia deliberada con `ingest_directory` (no recursivo, propaga la
    primera excepción y aborta el resto del lote — comportamiento correcto para
    el corpus chico y controlado de `docs/sample_evidence/`): esta función
    CONTINÚA con el resto de los archivos cuando uno falla (formato no
    soportado, extracción rota, PDF corrupto/encriptado, etc.). El fallo queda
    registrado como un `IngestionFailure` en la lista de resultados en vez de
    interrumpir el lote completo. Pensada para corpus grandes y heterogéneos
    (`docs/references/`, ~59 archivos) donde un solo archivo roto no debe
    bloquear la indexación de los demás.

    El recorrido es en orden alfabético por path relativo (determinístico,
    igual que `ingest_directory`).
    """
    collection = collection or get_collection()
    results: list[IngestionResult | IngestionFailure] = []
    files = sorted(
        (p for p in directory.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(directory).as_posix(),
    )
    for file_path in files:
        rel_source = file_path.relative_to(directory).as_posix()
        try:
            result = ingest_document(file_path, collection=collection, base_dir=directory)
        except Exception as exc:  # noqa: BLE001 - defensa amplia intencional: ver docstring
            results.append(
                IngestionFailure(
                    source=rel_source,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            continue
        results.append(result)
    return results
