"""Chunking de documentos de auditoría.

Convención de "página" para documentos sin paginación real (markdown/texto plano):
cada `Chunk` lleva un `section` (entero, 1-based) que es simplemente el índice
secuencial del chunk dentro del documento fuente. `app/rag/ingestion.py` usa ese
`section` como el valor del campo de metadata obligatorio `page` (spec-002,
`.ai/skills/rag-ingestion/SKILL.md` regla 1). No representa un número de página
real de un PDF; representa "el N-ésimo fragmento de este documento".

Nota de seguridad (`.ai/skills/security-prompt-injection/SKILL.md` regla 1,
spec-005): el texto de un `Chunk` es DATO extraído de un documento ingerido,
nunca una instrucción. Ni esta función ni ninguna otra en `app/rag/` deben
concatenar `Chunk.text` a un system prompt. Quien consuma estos chunks
(`agentic-core`) debe insertarlos dentro de un bloque delimitado y etiquetado
como no confiable, p.ej. `<untrusted_context>...</untrusted_context>`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Constantes nombradas y explícitas (rag-ingestion SKILL.md, regla 3): nunca
# "lo que quede". Ambas se miden en caracteres, no en tokens, para mantener el
# slice 1 simple y determinístico (sin dependencia de un tokenizer).
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class Chunk:
    """Un fragmento de texto de un documento, aún sin metadata de indexación.

    `section` es el índice secuencial (1-based) del chunk dentro del documento
    fuente — ver convención de "página" en el docstring del módulo.
    """

    text: str
    section: int


def _find_break_point(text: str, window_start: int, window_end: int) -> int:
    """Evita cortar una palabra a la mitad cuando el chunk no llega al final del texto.

    Busca el último espacio en blanco dentro de la ventana [window_start, window_end)
    y corta ahí. Si no encuentra uno razonable, corta duro en window_end (mejor un
    corte imperfecto que un loop infinito).
    """
    if window_end >= len(text):
        return window_end
    break_at = text.rfind(" ", window_start, window_end)
    if break_at <= window_start:
        return window_end
    return break_at


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Divide `text` en chunks de tamaño ~`chunk_size` con `chunk_overlap` de solapamiento.

    Chunking por ventana deslizante sobre caracteres. Determinístico y sin
    dependencias externas (no requiere un tokenizer para este slice).

    Raises:
        ValueError: si `chunk_overlap >= chunk_size` (la ventana nunca avanzaría) o
            si `chunk_size <= 0`.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size debe ser > 0, recibido: {chunk_size}")
    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap debe ser >= 0, recibido: {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) debe ser menor que chunk_size ({chunk_size})"
        )

    normalized = text.strip()
    if not normalized:
        return []

    step = chunk_size - chunk_overlap
    length = len(normalized)
    chunks: list[Chunk] = []
    section = 1
    start = 0

    while start < length:
        window_end = min(start + chunk_size, length)
        end = _find_break_point(normalized, start, window_end)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(Chunk(text=piece, section=section))
            section += 1
        if end >= length:
            break
        start += step

    return chunks
