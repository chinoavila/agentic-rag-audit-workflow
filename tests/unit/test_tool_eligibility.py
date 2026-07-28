"""Tests unitarios REALES (no skipeados) del helper único de elegibilidad de tools.

Cubre `app/services/tool_eligibility.py` -- la implementación de la Task 18 del plan de
permission modes (spec-013, filtro estructural de elegibilidad). Ver docstring del módulo bajo
test para el detalle del predicado.

DB de test aislada (sqlite:///:memory: + StaticPool), igual al patrón de
`tests/specs/conftest.py`, pero definida localmente porque `tests/unit/` no tiene conftest
propio y este módulo no necesita el resto de fixtures (cliente HTTP, Chroma) de `tests/specs`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.audit_case import AuditCase
from app.models.project_tool import ProjectTool
from app.models.tool_catalog_entry import ToolCatalogEntry
from app.services.tool_eligibility import is_tool_eligible, list_eligible_tools


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _catalog_entry(db: Session, key: str, installed: bool) -> ToolCatalogEntry:
    entry = ToolCatalogEntry(key=key, label=key, description="", installed=installed, actions=[])
    db.add(entry)
    db.commit()
    return entry


def _case(db: Session, name: str = "Caso de test") -> AuditCase:
    case = AuditCase(name=name)
    db.add(case)
    db.commit()
    return case


def _project_tool(db: Session, case_id: str, tool_key: str, enabled: bool) -> ProjectTool:
    row = ProjectTool(case_id=case_id, tool_key=tool_key, enabled=enabled, allowed_action_ids=[])
    db.add(row)
    db.commit()
    return row


class TestIsToolEligible:
    def test_installed_tool_without_project_tool_row_is_eligible_by_default(self, db: Session):
        """Caso 1 de spec-013: installed=True, sin fila ProjectTool -> elegible."""
        case = _case(db)
        _catalog_entry(db, "search_evidence", installed=True)

        assert is_tool_eligible(db, case.id, "search_evidence") is True

    def test_project_tool_enabled_false_excludes_installed_tool_for_that_case(self, db: Session):
        """Caso 2 de spec-013: installed=True, ProjectTool.enabled=False -> NO elegible."""
        case = _case(db)
        _catalog_entry(db, "search_evidence", installed=True)
        _project_tool(db, case.id, "search_evidence", enabled=False)

        assert is_tool_eligible(db, case.id, "search_evidence") is False

    def test_project_tool_enabled_true_keeps_installed_tool_eligible(self, db: Session):
        """Complemento del caso 2: un override explícito enabled=True sigue siendo elegible."""
        case = _case(db)
        _catalog_entry(db, "search_evidence", installed=True)
        _project_tool(db, case.id, "search_evidence", enabled=True)

        assert is_tool_eligible(db, case.id, "search_evidence") is True

    def test_tool_catalog_installed_false_excludes_tool_even_with_project_tool_enabled_true(
        self, db: Session
    ):
        """Caso 3 de spec-013: installed=False manda, aunque exista ProjectTool.enabled=True."""
        case = _case(db)
        _catalog_entry(db, "generate_report", installed=False)
        _project_tool(db, case.id, "generate_report", enabled=True)

        assert is_tool_eligible(db, case.id, "generate_report") is False

    def test_case_id_none_is_eligible_when_installed_true_no_project_tool_possible(self, db: Session):
        """Chat standalone (case_id=None): ProjectTool.case_id es FK NOT NULL a AuditCase, así
        que nunca puede existir una fila ProjectTool para case_id=None -- basta installed=True.
        """
        _catalog_entry(db, "search_evidence", installed=True)

        assert is_tool_eligible(db, None, "search_evidence") is True

    def test_case_id_none_not_eligible_when_installed_false(self, db: Session):
        """El catálogo global sigue mandando en el chat standalone: installed=False excluye."""
        _catalog_entry(db, "generate_report", installed=False)

        assert is_tool_eligible(db, None, "generate_report") is False

    def test_unknown_tool_key_is_not_eligible(self, db: Session):
        """Una tool_key ausente del catálogo global nunca es elegible."""
        assert is_tool_eligible(db, None, "tool_que_no_existe") is False


class TestListEligibleTools:
    def test_list_eligible_tools_applies_same_predicate_as_is_tool_eligible(self, db: Session):
        case = _case(db)
        _catalog_entry(db, "installed_default", installed=True)
        _catalog_entry(db, "installed_disabled_for_case", installed=True)
        _catalog_entry(db, "not_installed_globally", installed=False)
        _project_tool(db, case.id, "installed_disabled_for_case", enabled=False)
        _project_tool(db, case.id, "not_installed_globally", enabled=True)

        eligible_keys = {entry.key for entry in list_eligible_tools(db, case.id)}

        assert eligible_keys == {"installed_default"}
        # Consistencia cruzada con is_tool_eligible para cada key del catálogo.
        for key in ("installed_default", "installed_disabled_for_case", "not_installed_globally"):
            assert (key in eligible_keys) == is_tool_eligible(db, case.id, key)

    def test_list_eligible_tools_case_id_none_returns_all_installed(self, db: Session):
        _catalog_entry(db, "installed_a", installed=True)
        _catalog_entry(db, "installed_b", installed=True)
        _catalog_entry(db, "not_installed", installed=False)

        eligible_keys = {entry.key for entry in list_eligible_tools(db, None)}

        assert eligible_keys == {"installed_a", "installed_b"}

    def test_list_eligible_tools_empty_catalog_returns_empty_list(self, db: Session):
        assert list_eligible_tools(db, None) == []
        assert list_eligible_tools(db, "some-case-id") == []
