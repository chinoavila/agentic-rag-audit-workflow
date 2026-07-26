"""Script manual para ingerir `docs/references/` sin levantar la API.

`docs/references/` es el corpus real de normativa/estándares de auditoría
(COBIT5, ISO 27001/27002, MAGERIT, guías ISACA, cuestionarios, informes de
ejemplo, herramientas CAAT): ~59 archivos, ~52MB, recursivo en varias
subcarpetas (`Estandares/`, `Guias/`, `Analisis y Gestión de Riesgos/`,
`Ejemplo Cuestionarios/`, `Herramientas CAats/` -- incluida su subcarpeta
`ejemplos_CAATs/` --, `ejemplos_informes/`), en su mayoría PDF (hasta 17MB
cada uno), más un `.docx` y un `.xlsx`.

Uso (dentro del contenedor, para que `CHROMA_PERSIST_DIR` apunte al volumen
Docker montado y no a un path efímero del host, y para que `docs/references/`
exista vía el bind mount `./docs/references:/app/docs/references:ro` de
`docker-compose.yml`):

    docker compose exec backend python -m app.rag.ingest_references

A diferencia de `ingest_sample.py` (usa `app.rag.ingestion.ingest_directory`:
no recursivo, falla explícito y aborta todo el lote ante el primer archivo no
soportado -- correcto para el corpus chico y controlado de
`docs/sample_evidence/`), este script usa
`app.rag.ingestion.ingest_directory_recursive`: camina subcarpetas y CONTINÚA
con el resto del lote si un archivo puntual falla (formato no soportado,
extracción rota, PDF corrupto/encriptado, etc.) -- el fallo queda listado al
final, no tumba la ingesta de los otros ~58 archivos.

Por el tamaño del corpus, correr esto puede tardar varios minutos reales; se
imprime progreso por archivo a medida que avanza (no solo un resumen al
final). Es idempotente (spec-002): correrlo más de una vez sobre el mismo
contenido no duplica chunks -- interrumpirlo a mitad de camino y volver a
correrlo es seguro (los archivos ya indexados quedan en `skipped_unchanged`).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from app.rag.ingestion import IngestionFailure, IngestionResult, ingest_directory_recursive

REFERENCE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "references"


def main() -> int:
    if not REFERENCE_DOCS_DIR.is_dir():
        print(f"[ingest_references] No existe el directorio: {REFERENCE_DOCS_DIR}", file=sys.stderr)
        return 1

    print(f"[ingest_references] Ingiriendo recursivamente: {REFERENCE_DOCS_DIR}")
    started = time.monotonic()

    inserted = replaced = skipped = failed = 0
    total_chunks = 0

    for result in ingest_directory_recursive(REFERENCE_DOCS_DIR):
        if isinstance(result, IngestionFailure):
            failed += 1
            print(
                f"[ingest_references] FAILED {result.source}: "
                f"{result.error_type}: {result.error_message}",
                file=sys.stderr,
            )
            continue

        assert isinstance(result, IngestionResult)  # narrowing para mypy/lectura
        total_chunks += result.chunks_indexed
        if result.status == "inserted":
            inserted += 1
        elif result.status == "replaced":
            replaced += 1
        elif result.status == "skipped_unchanged":
            skipped += 1

        print(
            f"[ingest_references] {result.source}: status={result.status} "
            f"chunks_indexed={result.chunks_indexed} doc_hash={result.doc_hash[:12]}..."
        )

    elapsed = time.monotonic() - started
    print(
        f"[ingest_references] Done in {elapsed:.1f}s -- "
        f"inserted={inserted} replaced={replaced} skipped_unchanged={skipped} "
        f"failed={failed} total_chunks_indexed={total_chunks}"
    )

    # Exit code distinto de cero si hubo al menos un fallo parcial: el proceso
    # igual terminó (no se abortó a mitad de camino), pero conviene que quien
    # lo dispara en CI/onboarding se entere sin tener que leer el log entero.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
