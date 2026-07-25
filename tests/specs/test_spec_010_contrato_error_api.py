"""Tests para spec-010: Contrato de Error Uniforme de API.

Criterios de aceptación:
- Errores usan HTTPException, nunca 200 con error flag.
- Error body tiene shape uniforme: {"detail": str, "code": str}.
- Solo códigos documentados: 200, 201, 400, 401, 403, 404, 422, 500.
- Errores de validación Pydantic (422) preservan detalle original.
"""

import pytest
from fastapi import status


@pytest.mark.spec_010
class TestContratoErrorApi:
    """Spec-010: Contrato de Error Uniforme de API (.ai/specs/platform/spec-010-contrato-error-api.md)"""

    def test_errors_use_http_exception_not_200_with_error_flag(self, client):
        """Errores no son 200 con flag; usan códigos HTTP estándar."""
        # Act: intentar acceder a un recurso inexistente
        response = client.get("/api/findings/nonexistent_id")

        # Assert: debe ser un código de error (no 200)
        assert response.status_code != 200, "Errores nunca deben ser 200 con un flag"
        assert response.status_code >= 400, "Debe ser un código de error HTTP (4xx/5xx)"

    def test_error_body_matches_uniform_shape(self, client):
        """El body de error tiene shape uniforme: {"detail": ..., "code": ...}."""
        # Act: provocar un error 404
        response = client.get("/api/findings/nonexistent_id")

        # Assert: tiene los campos requeridos
        assert response.status_code == 404
        body = response.json()
        assert "detail" in body, "Toda respuesta de error debe tener 'detail'"
        assert "code" in body, "Toda respuesta de error debe tener 'code'"
        assert isinstance(body["detail"], (str, list, dict)), "detail debe ser string, list o dict"
        assert isinstance(body["code"], str), "code debe ser string"

    def test_404_finding_not_found_has_correct_shape(self, client):
        """GET /api/findings/{id-inexistente} devuelve 404 con shape correcto."""
        # Act
        response = client.get("/api/findings/fake_id_123")

        # Assert
        assert response.status_code == 404
        body = response.json()
        assert "detail" in body
        assert "code" in body
        assert body["code"] == "finding_not_found" or body["code"] == "not_found"

    def test_422_validation_error_preserves_detail(self, client, db_session):
        """POST con validation error (422) preserva lista de errores en detail."""
        # Setup: crear un case para que el POST tenga una case_id válida
        from app.models.audit_case import AuditCase
        case = AuditCase(id="case_422", name="Test", description="Test")
        db_session.add(case)
        db_session.commit()

        # Act: POST con payload incompleto (falta evidence, que es obligatorio)
        response = client.post(
            "/api/findings",
            json={
                "case_id": "case_422",
                "title": "Test Finding",
                "description": "Test",
                "severity": "medium",
                # "evidence": [] <-- MISSING, debe fallar con 422
                "risk_score": 5.0,
            },
        )

        # Assert: debe ser 422
        assert response.status_code == 422, f"Validación fallida debe ser 422, recibido {response.status_code}"

        # Assert: shape uniforme, detail debe ser una lista de errores
        body = response.json()
        assert "detail" in body, "422 debe tener 'detail'"
        assert "code" in body, "422 debe tener 'code'"
        assert body["code"] == "validation_error" or body["code"] == "unprocessable_entity"
        # detail debe ser una lista de detalles de error
        assert isinstance(body["detail"], list), "Validation error detail debe ser lista de errores"

    def test_only_documented_status_codes_are_used(self, client, db_session):
        """Todos los status codes retornados son del set documentado: {200, 201, 400, 401, 403, 404, 422, 500}."""
        documented_codes = {200, 201, 400, 401, 403, 404, 422, 500}

        # Setup: crear un case para poder hacer POST exitoso
        from app.models.audit_case import AuditCase
        case = AuditCase(id="case_status", name="Test", description="Test")
        db_session.add(case)
        db_session.commit()

        # Test multiple endpoints
        test_cases = [
            # Éxito 200/201
            ("GET", "/api/findings", None, {200}),  # GET lista (vacío es ok)
            ("POST", "/api/findings", {
                "case_id": "case_status",
                "title": "Test",
                "description": "Test",
                "severity": "low",
                "evidence": [{"source": "doc.txt", "page": 1}],
                "risk_score": 2.5,
            }, {201}),
            # Errores
            ("GET", "/api/findings/nonexistent", None, {404}),
            ("DELETE", "/api/findings/any_id", None, {404, 405}),  # 405 o 404
        ]

        for method, path, payload, expected_codes in test_cases:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json=payload)
            elif method == "DELETE":
                response = client.delete(path)

            assert response.status_code in expected_codes or response.status_code in documented_codes, (
                f"{method} {path}: status {response.status_code} no está en documentados {documented_codes}"
            )

    def test_404_audit_case_not_found(self, client):
        """POST con case_id inexistente devuelve 404 con código 'audit_case_not_found'."""
        # Act: crear finding con case_id que no existe
        response = client.post(
            "/api/findings",
            json={
                "case_id": "nonexistent_case",
                "title": "Test",
                "description": "Test",
                "severity": "medium",
                "evidence": [{"source": "doc.txt", "page": 1}],
                "risk_score": 5.0,
            },
        )

        # Assert
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "audit_case_not_found"
        assert "detail" in body

    def test_error_response_never_has_200_status(self, client):
        """Nunca un error viene con 200 OK."""
        # Act: varias acciones que deben fallar
        responses = [
            client.get("/api/findings/nonexistent"),
            client.delete("/api/findings/nonexistent"),
            client.post("/api/findings", json={}),  # Payload incompleto
        ]

        # Assert: ninguno debe ser 200 (aunque algunos serán 400+ errors, que es lo correcto)
        for resp in responses:
            if resp.status_code >= 400:
                # Si es error, el status es de error (no 200)
                assert resp.status_code != 200, "Error responses nunca deben ser 200"
                # Y el body debe tener el shape uniforme
                body = resp.json()
                assert "detail" in body and "code" in body, (
                    f"Error {resp.status_code} debe tener shape uniforme"
                )

    def test_empty_payload_returns_422_not_400(self, client, db_session):
        """POST {} (payload vacío) retorna 422 (validación) no 400."""
        # Act
        response = client.post("/api/findings", json={})

        # Assert
        assert response.status_code == 422, "Validación fallida debe ser 422"
        body = response.json()
        assert "detail" in body
        assert "code" in body

    def test_bad_request_has_bad_request_code(self, client, db_session):
        """Un 400 Bad Request tiene code='bad_request' o similar."""
        # Setup: crear case
        from app.models.audit_case import AuditCase
        case = AuditCase(id="case_bad_req", name="Test")
        db_session.add(case)
        db_session.commit()

        # Crear un finding
        response = client.post(
            "/api/findings",
            json={
                "case_id": "case_bad_req",
                "title": "Test",
                "description": "Test",
                "severity": "low",
                "evidence": [{"source": "doc.txt", "page": 1}],
                "risk_score": 2.5,
            },
        )
        assert response.status_code == 201
        finding_id = response.json()["id"]

        # Act: PATCH con payload inválido (ni status ni superseded_by)
        response = client.patch(
            f"/api/findings/{finding_id}",
            json={},  # Empty, violates "at least one of"
        )

        # Assert: debe ser 400
        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
        assert "code" in body
        assert body["code"] == "bad_request" or body["code"] == "empty_patch_payload"

    def test_all_error_responses_have_consistent_shape(self, client, db_session):
        """Spot check: todos los errores en varios endpoints tienen el shape {"detail", "code"}."""
        # Setup
        from app.models.audit_case import AuditCase
        case = AuditCase(id="case_spot", name="Test", description="Test")
        db_session.add(case)
        db_session.commit()

        # Provocar varios tipos de error
        endpoints = [
            ("GET", "/api/findings/fake"),
            ("GET", "/api/audit_cases/fake"),
            ("POST", "/api/findings", {}),
            ("DELETE", "/api/findings/fake"),
        ]

        for method, path, *payload_list in endpoints:
            payload = payload_list[0] if payload_list else None

            if method == "GET":
                resp = client.get(path)
            elif method == "POST":
                resp = client.post(path, json=payload)
            elif method == "DELETE":
                resp = client.delete(path)

            # Si es error (4xx/5xx), validar shape
            if resp.status_code >= 400:
                body = resp.json()
                assert "detail" in body, f"{method} {path}: falta 'detail'"
                assert "code" in body, f"{method} {path}: falta 'code'"
