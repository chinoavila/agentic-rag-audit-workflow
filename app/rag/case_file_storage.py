"""Blob storage local (emulado) para los archivos que un humano adjunta a un proyecto
(`CaseFile`, spec-020). Mismo patrón que `app/reports/storage.py`: un directorio en disco,
namespaced por `case_id` para no colisionar entre proyectos con archivos del mismo nombre.
"""

from __future__ import annotations

import os
from pathlib import Path

CASE_FILES_DIR = Path(os.environ.get("CASE_FILES_DIR", "./dev_case_files"))


def write_case_file_blob(case_id: str, file_id: str, filename: str, content: bytes) -> str:
    """Escribe el archivo a disco y devuelve su `blob_path` (relativo a `CASE_FILES_DIR`)."""
    case_dir = CASE_FILES_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix
    relative_path = f"{case_id}/{file_id}{suffix}"
    (CASE_FILES_DIR / relative_path).write_bytes(content)
    return relative_path
