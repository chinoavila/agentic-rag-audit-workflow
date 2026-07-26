"""Fixtures compartidas para los tests de specs SDD (.ai/specs/**).

DB de test aislada (sqlite:///:memory:), vector store in-memory, cliente HTTP de test.
"""

from __future__ import annotations

from pathlib import Path

import chromadb
import pytest
from chromadb.config import Settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.rag.vectorstore import COLLECTION_NAME, EMBEDDING_FUNCTION


@pytest.fixture(scope="function")
def db_engine():
    """Engine de SQLite in-memory aislado por test.

    StaticPool es obligatorio: sin él, cada checkout de conexión (p. ej. desde el
    thread worker donde FastAPI corre los endpoints sync via run_in_threadpool)
    abre una base :memory: nueva y vacía, perdiendo las tablas creadas abajo.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Sesión de SQLAlchemy sobre la DB in-memory."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def app_with_test_db(db_session):
    """FastAPI app con DB de test inyectada."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app_with_test_db):
    """Cliente HTTP de test contra el app con DB de test."""
    return TestClient(app_with_test_db)


@pytest.fixture(scope="function")
def chroma_client():
    """Cliente Chroma in-memory (EphemeralClient) para tests.

    chromadb cachea el System subyacente por proceso cuando los Settings son
    idénticos, así que dos `EphemeralClient()` "nuevos" dentro de la misma
    sesión de pytest terminan compartiendo el mismo almacenamiento en memoria
    y filtran datos de un test a otro (misma COLLECTION_NAME). `reset()` al
    finalizar cada test corta esa fuga; requiere `allow_reset=True`.
    """
    client = chromadb.EphemeralClient(settings=Settings(allow_reset=True))
    yield client
    client.reset()


@pytest.fixture(scope="function")
def test_collection(chroma_client):
    """Colección Chroma in-memory con el modelo de embeddings real."""
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
        metadata={
            "embedding_model": "all-MiniLM-L6-v2",
            "domain": "audit_docs",
            "hnsw:space": "cosine",
        },
    )


@pytest.fixture(scope="function")
def test_doc_path(tmp_path: Path) -> Path:
    """Directorio temporal para documentos de test."""
    return tmp_path
