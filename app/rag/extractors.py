"""Extracción de texto para formatos binarios de `docs/references/` (PDF, DOCX, XLSX).

Los `.md`/`.txt` no pasan por este módulo (siguen decodificándose directo en
`app/rag/ingestion.py::load_document`); este módulo cubre los formatos agregados
para poder indexar el corpus real de normativa/estándares de auditoría en
`docs/references/` (COBIT5, ISO 27001/27002, MAGERIT, guías ISACA, cuestionarios,
informes de ejemplo, herramientas CAAT).

SEGURIDAD (spec-005, `.ai/skills/security-prompt-injection/SKILL.md`): igual que en
`ingestion.py`/`chunking.py`, el texto que devuelven estas funciones es DATO
extraído de un documento ingerido, nunca una instrucción — estas funciones no
interpretan ni ejecutan nada del contenido, solo lo extraen como texto plano.

Tolerancia a fallos parciales (ver `app/rag/ingestion.py::_extract_units`):
- PDF: si una página individual falla al extraer texto (escaneada como imagen sin
  texto embebido, stream corrupto, etc.), se registra un `logger.warning`/`info` y
  esa página se devuelve con texto vacío en vez de abortar el documento entero
  (pypdf no hace OCR: una página escaneada como imagen produce texto vacío de forma
  esperada, no es un error). Si el PDF completo no se puede abrir (encriptado sin
  password que pypdf pueda descifrar, corrupto a nivel de contenedor), se levanta
  `ExtractionError` — ese archivo puntual falla, pero quien orquesta la ingesta en
  lote (`ingest_directory_recursive`) sigue con el resto de los archivos.
- DOCX/XLSX: si el archivo no se puede abrir, se levanta `ExtractionError`.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ExtractionError(ValueError):
    """El archivo tiene una extensión soportada pero no se pudo extraer su contenido.

    Cubre tanto "la librería de extracción no está instalada" como "el archivo no
    se pudo abrir" (corrupto, encriptado sin password, etc.).
    """


def extract_pdf_pages(file_path: Path) -> list[tuple[int, str]]:
    """Extrae texto por página de un PDF: `[(page_num_1_based, texto), ...]`.

    El número de página es el número de página PDF REAL (1-based), a diferencia
    de la convención de "índice secuencial de fragmento" que usa `chunk_text()`
    para `.md`/`.txt`/`.docx`/`.xlsx` (ver `app/rag/chunking.py`).

    Una página cuya extracción individual falla (o que simplemente no tiene texto
    embebido, p. ej. una página escaneada como imagen) se devuelve con texto vacío
    (`""`) en vez de abortar el documento completo — `app/rag/ingestion.py` filtra
    naturalmente las páginas vacías (`chunk_text("")` devuelve `[]`, sin chunks
    para esa página).

    Raises:
        ExtractionError: si el PDF completo no se puede abrir (corrupto, o
            encriptado con un password que no sea el vacío).
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - depende de deps instaladas en Docker
        raise ExtractionError(
            "La librería 'pypdf' no está instalada; no se puede extraer texto de PDF."
        ) from exc

    try:
        reader = PdfReader(str(file_path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise ExtractionError(f"No se pudo abrir el PDF '{file_path.name}': {exc}") from exc

    if reader.is_encrypted:
        try:
            decrypt_result = reader.decrypt("")
        except Exception as exc:  # pypdf lanza distintas excepciones según el backend de cifrado
            raise ExtractionError(
                f"PDF encriptado y no se pudo desencriptar sin password: "
                f"'{file_path.name}' ({exc})"
            ) from exc
        if not decrypt_result:
            raise ExtractionError(
                f"PDF encriptado con password requerido (no se pudo abrir con password "
                f"vacío): '{file_path.name}'"
            )

    pages: list[tuple[int, str]] = []
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - defensa amplia intencional: ver docstring del módulo
            logger.warning(
                "No se pudo extraer texto de la pagina %s de '%s': %s. Se indexa como vacia.",
                page_num,
                file_path.name,
                exc,
            )
            text = ""
        if not text.strip():
            logger.info(
                "Pagina %s de '%s' no produjo texto (posible pagina escaneada/imagen).",
                page_num,
                file_path.name,
            )
        pages.append((page_num, text))
    return pages


def extract_docx_text(file_path: Path) -> str:
    """Extrae y concatena el texto de todos los párrafos de un `.docx`.

    No hay concepto de "página" real recuperable sin renderizar el documento (Word
    no guarda saltos de página como metadata fiable) — no se inventa una. Quien
    llama a esta función (`app/rag/ingestion.py`) usa el índice secuencial de
    chunk como `page`, misma convención que `.md`/`.txt`.

    Raises:
        ExtractionError: si el archivo no se puede abrir (corrupto, no es
            realmente un .docx válido, etc.).
    """
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - depende de deps instaladas en Docker
        raise ExtractionError(
            "La librería 'python-docx' no está instalada; no se puede extraer texto de DOCX."
        ) from exc

    try:
        document = Document(str(file_path))
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de apertura es fatal para este archivo
        raise ExtractionError(f"No se pudo abrir el DOCX '{file_path.name}': {exc}") from exc

    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)


def extract_xlsx_text(file_path: Path) -> str:
    """Representa un `.xlsx` como texto plano: por hoja, nombre de hoja + filas.

    Tampoco hay "página" real (una hoja puede tener cualquier cantidad de filas) —
    quien llama a esta función usa el índice secuencial de chunk como `page`,
    misma convención que `.md`/`.txt`/`.docx`.

    Raises:
        ExtractionError: si el archivo no se puede abrir (corrupto, no es
            realmente un .xlsx válido, etc.).
    """
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - depende de deps instaladas en Docker
        raise ExtractionError(
            "La librería 'openpyxl' no está instalada; no se puede extraer texto de XLSX."
        ) from exc

    try:
        workbook = load_workbook(filename=str(file_path), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de apertura es fatal para este archivo
        raise ExtractionError(f"No se pudo abrir el XLSX '{file_path.name}': {exc}") from exc

    lines: list[str] = []
    try:
        for sheet in workbook.worksheets:
            lines.append(f"# Hoja: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = [str(v) for v in row if v is not None]
                if values:
                    lines.append(" | ".join(values))
    finally:
        workbook.close()

    return "\n".join(lines)
