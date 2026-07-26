"""Tests para spec-012: Contrato de Generación de Informes desde Plantilla.

Criterios de aceptación:
- `generate_report` declara input_schema y valida el input antes de ejecutar (spec-003).
- El LLM completa únicamente los placeholders de prosa definidos por la plantilla; no puede
  alterar estructura, encabezados ni tablas fijas.
- Cada afirmación de la narrativa cita el hallazgo/evidencia de origen (spec-001).
- Si alguna rúbrica falla, no se publica nada y se retorna feedback estructurado.
- Ningún informe se persiste como "published" sin pasar la aprobación humana de spec-006.
"""

from __future__ import annotations

import pytest

from app.models.audit_case import AuditCase
from app.models.finding import Finding
from app.models.report import Report
from app.reports import storage as storage_module
from app.tools.generate_report import generate_report

TEMPLATE_ID = "auditoria_estandar"
# Placeholders declarados por docs/report_templates/auditoria_estandar.md.
ALL_PLACEHOLDERS = ("resumen_ejecutivo", "hallazgos_detalle", "recomendaciones")


@pytest.fixture()
def report_blob_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "REPORTS_BLOB_DIR", tmp_path)
    return tmp_path


def _make_case_with_grounded_finding(db_session, *, case_id: str) -> tuple[AuditCase, dict]:
    """Crea un `AuditCase` con un `Finding` cuya evidencia sirve como cita válida para las
    secciones de un `generate_report` de test (grounding, mismo contrato que spec-001).
    """
    case = AuditCase(id=case_id, name=f"Caso {case_id}")
    db_session.add(case)
    finding = Finding(
        case_id=case_id,
        title="Hallazgo de respaldo",
        description="Hallazgo usado como evidencia del informe.",
        severity="high",
        evidence=[{"source": "doc_evidencia.txt", "page": 2}],
        risk_score=7.5,
        status="pending_review",
    )
    db_session.add(finding)
    db_session.commit()
    return case, {"source": "doc_evidencia.txt", "page": 2}


def _section(placeholder: str, citation: dict, *, narrative: str | None = None) -> dict:
    return {
        "placeholder": placeholder,
        "narrative": narrative or f"Narrativa para {placeholder}.",
        "citations": [citation],
    }


@pytest.mark.spec_012
class TestGeneracionInformesPlantilla:
    """Spec-012: Contrato de Generación de Informes desde Plantilla (.ai/specs/audit/spec-012-generacion-informes-plantilla.md)"""

    def test_generate_report_rejects_invalid_input_schema(self, db_session, report_blob_dir):
        # Falta case_id/template_id/title, y sections trae una entrada sin `citations`
        # (violación del input_schema, spec-003).
        result = generate_report(
            {"sections": [{"placeholder": "resumen_ejecutivo", "narrative": "texto"}]},
            db=db_session,
        )

        assert result["code"] == "invalid_input"
        assert db_session.query(Report).count() == 0

    def test_llm_cannot_modify_template_structure_outside_placeholders(
        self, db_session, report_blob_dir
    ):
        case, citation = _make_case_with_grounded_finding(db_session, case_id="case_spec012_a")

        result = generate_report(
            {
                "case_id": case.id,
                "template_id": TEMPLATE_ID,
                "title": "Informe con placeholder inventado",
                "sections": [
                    _section("resumen_ejecutivo", citation),
                    _section("hallazgos_detalle", citation),
                    _section("recomendaciones", citation),
                    # No es un placeholder real de la plantilla: intento de agregar una
                    # sección/estructura que la plantilla no declaró.
                    _section("seccion_inventada_por_el_llm", citation),
                ],
            },
            db=db_session,
        )

        assert result["code"] == "rubric_failed"
        completeness = next(
            c for c in result["rubric_results"]["checks"] if c["name"] == "completeness"
        )
        assert completeness["passed"] is False
        assert "seccion_inventada_por_el_llm" in completeness["detail"]
        assert db_session.query(Report).count() == 0, "Nada debe persistirse si falla la rúbrica"

    def test_narrative_sections_cite_source_findings(self, db_session, report_blob_dir):
        case, _ = _make_case_with_grounded_finding(db_session, case_id="case_spec012_b")
        fabricated_citation = {"source": "documento_que_no_existe.txt", "page": 99}

        result = generate_report(
            {
                "case_id": case.id,
                "template_id": TEMPLATE_ID,
                "title": "Informe con cita no respaldada",
                "sections": [
                    _section(name, fabricated_citation) for name in ALL_PLACEHOLDERS
                ],
            },
            db=db_session,
        )

        assert result["code"] == "rubric_failed"
        citations_check = next(
            c for c in result["rubric_results"]["checks"] if c["name"] == "valid_citations"
        )
        assert citations_check["passed"] is False
        assert db_session.query(Report).count() == 0

    def test_rubric_failure_blocks_publication_with_structured_feedback(
        self, db_session, report_blob_dir
    ):
        case, citation = _make_case_with_grounded_finding(db_session, case_id="case_spec012_c")

        # Falta la sección "recomendaciones": viola completitud.
        result = generate_report(
            {
                "case_id": case.id,
                "template_id": TEMPLATE_ID,
                "title": "Informe incompleto",
                "sections": [
                    _section("resumen_ejecutivo", citation),
                    _section("hallazgos_detalle", citation),
                ],
            },
            db=db_session,
        )

        assert result["code"] == "rubric_failed"
        assert result["rubric_results"]["passed"] is False
        completeness = next(
            c for c in result["rubric_results"]["checks"] if c["name"] == "completeness"
        )
        assert completeness["passed"] is False
        assert "recomendaciones" in completeness["detail"]
        # Feedback reutilizable para un reintento: retry con la sección faltante agregada.
        result_retry = generate_report(
            {
                "case_id": case.id,
                "template_id": TEMPLATE_ID,
                "title": "Informe corregido",
                "sections": [_section(name, citation) for name in ALL_PLACEHOLDERS],
            },
            db=db_session,
        )
        assert "error" not in result_retry
        assert db_session.query(Report).count() == 1

    def test_report_requires_human_approval_before_persisted_as_published(
        self, db_session, client, report_blob_dir
    ):
        case, citation = _make_case_with_grounded_finding(db_session, case_id="case_spec012_d")

        result = generate_report(
            {
                "case_id": case.id,
                "template_id": TEMPLATE_ID,
                "title": "Informe listo para aprobar",
                "sections": [_section(name, citation) for name in ALL_PLACEHOLDERS],
            },
            db=db_session,
        )

        assert "error" not in result
        assert result["status"] == "pending_review", "Nunca se persiste directo como published"
        report_id = result["report_id"]

        rejected = client.patch(f"/api/reports/{report_id}", json={"status": "published"})
        assert rejected.status_code == 400
        assert rejected.json()["code"] == "approval_required"

        approved = client.patch(
            f"/api/reports/{report_id}",
            json={"status": "published", "approved_by": "auditor-humano-1"},
        )
        assert approved.status_code == 200
        data = approved.json()
        assert data["status"] == "published"
        assert data["approved_by"] == "auditor-humano-1"
        assert data["approved_at"] is not None
