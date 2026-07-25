"""Script manual para ingerir `docs/sample_evidence/` sin levantar la API.

Uso (dentro del contenedor, para que `CHROMA_PERSIST_DIR` apunte al volumen
Docker montado y no a un path efímero del host):

    docker compose exec backend python -m app.rag.ingest_sample

Reutiliza exactamente la misma función (`app.rag.ingestion.ingest_directory`)
que usa `POST /api/rag/ingest` (`app/routers/rag_retrieval.py`) — se ofrecen
ambas vías (script y endpoint) porque el script no requiere que uvicorn esté
arriba (útil para seed inicial en CI/onboarding), y el endpoint es más cómodo
para re-disparar la ingesta manualmente desde Swagger/curl durante desarrollo.
Es idempotente (spec-002): correrlo más de una veces sobre el mismo contenido
no duplica chunks.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.rag.ingestion import UnsupportedFormatError, ingest_directory

SAMPLE_EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "sample_evidence"


def main() -> int:
    if not SAMPLE_EVIDENCE_DIR.is_dir():
        print(f"[ingest_sample] No existe el directorio: {SAMPLE_EVIDENCE_DIR}", file=sys.stderr)
        return 1

    try:
        results = ingest_directory(SAMPLE_EVIDENCE_DIR)
    except UnsupportedFormatError as exc:
        print(f"[ingest_sample] Formato no soportado: {exc}", file=sys.stderr)
        return 1

    for result in results:
        print(
            f"[ingest_sample] {result.source}: status={result.status} "
            f"chunks_indexed={result.chunks_indexed} doc_hash={result.doc_hash[:12]}..."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
