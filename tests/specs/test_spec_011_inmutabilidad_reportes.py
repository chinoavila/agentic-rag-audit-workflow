"""Tests para spec-011: Inmutabilidad de Reportes Generados.

Criterios de aceptación:
- Ningún modelo Report expone una operación de DELETE física.
- Regenerar/corregir un reporte crea una fila nueva referenciando la anterior via
  superseded_by; la fila anterior conserva id/created_at/blob_path intactos.
- El archivo en blob storage de un reporte superseded no se borra físicamente.
- created_at nunca se modifica tras la creación; updated_at cambia en cada transición.
- El historial completo de versiones (incluyendo superseded) es recuperable vía API.
"""

from __future__ import annotations

import time

import pytest

from app.models.audit_case import AuditCase
from app.models.report import Report
from app.reports import storage as storage_module
from app.reports.storage import write_report_blob


@pytest.fixture()
def report_blob_dir(tmp_path, monkeypatch):
    """Aísla el blob storage de reportes a un directorio temporal por test (evita que los
    tests escriban en `./dev_reports_blob` real ni se pisen entre sí).
    """
    monkeypatch.setattr(storage_module, "REPORTS_BLOB_DIR", tmp_path)
    return tmp_path


def _make_report(db_session, *, case_id: str, title: str = "Informe de test") -> Report:
    """Crea y persiste un `Report` directamente vía ORM (equivalente al efecto de
    `generate_report` una vez que ya pasó las rúbricas), incluyendo su blob real en disco --
    mismo criterio que `test_spec_004_inmutabilidad_audit_trail.py` usa para `Finding`.
    """
    report = Report(
        case_id=case_id,
        template_id="auditoria_estandar",
        title=title,
        status="pending_review",
        blob_path="",
        sections=[
            {
                "placeholder": "resumen_ejecutivo",
                "narrative": "Resumen de prueba.",
                "citations": [{"source": "doc.txt", "page": 1}],
            }
        ],
        rubric_results={"passed": True, "checks": []},
    )
    db_session.add(report)
    db_session.flush()
    report.blob_path = write_report_blob(report.id, f"# {title}\n\nResumen de prueba.")
    db_session.commit()
    db_session.refresh(report)
    return report


@pytest.mark.spec_011
class TestInmutabilidadReportes:
    """Spec-011: Inmutabilidad de Reportes Generados (.ai/specs/audit/spec-011-inmutabilidad-reportes.md)"""

    def test_no_physical_delete_endpoint_exists_for_reports(self, client):
        response = client.delete("/api/reports/nonexistent_id")

        assert response.status_code in (404, 405), (
            f"DELETE /api/reports/{{id}} no debería existir; recibido {response.status_code}"
        )

    def test_regenerating_report_supersedes_without_deleting_blob(
        self, db_session, client, report_blob_dir
    ):
        case = AuditCase(id="case_spec011_a", name="Caso spec-011 a")
        db_session.add(case)
        db_session.commit()

        original = _make_report(db_session, case_id=case.id, title="Informe original")
        replacement = _make_report(db_session, case_id=case.id, title="Informe corregido")

        original_blob_path = original.blob_path
        original_blob_file = report_blob_dir / original_blob_path
        assert original_blob_file.is_file(), "El blob del reporte original debe existir antes del supersede"

        response = client.patch(
            f"/api/reports/{original.id}", json={"superseded_by": replacement.id}
        )

        assert response.status_code == 200
        db_session.expire_all()
        original_after = db_session.get(Report, original.id)
        assert original_after.superseded_by == replacement.id
        assert original_after.blob_path == original_blob_path, "blob_path no debe cambiar al supersederse"
        assert original_blob_file.is_file(), "El archivo del reporte supersedido NO debe borrarse físicamente"
        assert original_blob_file.read_text(encoding="utf-8") == "# Informe original\n\nResumen de prueba."

    def test_created_at_immutable_after_creation(self, db_session, client, report_blob_dir):
        case = AuditCase(id="case_spec011_b", name="Caso spec-011 b")
        db_session.add(case)
        db_session.commit()

        report = _make_report(db_session, case_id=case.id)
        original_created_at = report.created_at

        response = client.patch(f"/api/reports/{report.id}", json={"status": "rejected"})

        assert response.status_code == 200
        db_session.expire_all()
        report_after = db_session.get(Report, report.id)
        assert report_after.created_at == original_created_at, "created_at debe ser inmutable tras PATCH"

    def test_updated_at_changes_on_supersede(self, db_session, client, report_blob_dir):
        case = AuditCase(id="case_spec011_c", name="Caso spec-011 c")
        db_session.add(case)
        db_session.commit()

        report1 = _make_report(db_session, case_id=case.id, title="v1")
        report2 = _make_report(db_session, case_id=case.id, title="v2")
        original_updated_at = report1.updated_at

        time.sleep(0.01)
        response = client.patch(f"/api/reports/{report1.id}", json={"superseded_by": report2.id})

        assert response.status_code == 200
        db_session.expire_all()
        report1_after = db_session.get(Report, report1.id)
        assert report1_after.updated_at >= original_updated_at

    def test_full_version_history_of_report_is_retrievable(
        self, db_session, client, report_blob_dir
    ):
        case = AuditCase(id="case_spec011_d", name="Caso spec-011 d")
        db_session.add(case)
        db_session.commit()

        report_v1 = _make_report(db_session, case_id=case.id, title="Informe v1")
        report_v2 = _make_report(db_session, case_id=case.id, title="Informe v2")

        supersede = client.patch(
            f"/api/reports/{report_v1.id}", json={"superseded_by": report_v2.id}
        )
        assert supersede.status_code == 200

        response = client.get(f"/api/reports/{report_v1.id}")
        assert response.status_code == 200, "El reporte supersedido debe ser recuperable"
        data = response.json()
        assert data["id"] == report_v1.id
        assert data["superseded_by"] == report_v2.id
        assert data["title"] == "Informe v1", "Contenido original debe ser intacto"

        listing = client.get(f"/api/reports?case_id={case.id}")
        assert listing.status_code == 200
        report_ids = {r["id"] for r in listing.json()}
        assert report_v1.id in report_ids, "v1 debe aparecer en el listado (no borrado)"
        assert report_v2.id in report_ids

        content = client.get(f"/api/reports/{report_v1.id}/content")
        assert content.status_code == 200
        assert "Informe v1" in content.json()["content"]
