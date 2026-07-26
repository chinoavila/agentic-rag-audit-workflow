"""Tests para spec-006: Human-in-the-Loop para Hallazgos de Alto Riesgo.

Criterios de aceptación:
- Un hallazgo high/critical creado entra en pending_review, nunca directo a final.
- pending_review -> final requiere approved_by y approved_at no nulos.
- Un hallazgo low/medium puede llegar a final sin aprobación explícita.
- La UI (Chainlit) expone una acción explícita de aprobar/rechazar para pending_review.
- Rechazar un hallazgo en pending_review lo marca status=rejected sin perder el registro.
"""

from __future__ import annotations

import pytest

from app.agentic_core.loop import ToolCallRecord
from app.models.audit_case import AuditCase
from app.models.finding import Finding


def _finding_payload(*, case_id: str, severity: str, title: str = "Hallazgo de test") -> dict:
    return {
        "case_id": case_id,
        "title": title,
        "description": "Descripción de test",
        "severity": severity,
        "evidence": [{"source": "doc.txt", "page": 1}],
        "risk_score": 7.5 if severity in ("high", "critical") else 2.5,
    }


@pytest.mark.spec_006
class TestHumanInTheLoop:
    """Spec-006: Human-in-the-Loop para Hallazgos de Alto Riesgo (.ai/specs/audit/spec-006-human-in-the-loop.md)"""

    def test_high_severity_finding_starts_as_pending_review(self, db_session, client):
        case = AuditCase(id="case_spec006_a", name="Caso spec-006 a")
        db_session.add(case)
        db_session.commit()

        response = client.post(
            "/api/findings", json=_finding_payload(case_id=case.id, severity="high")
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending_review"
        assert data["approved_by"] is None
        assert data["approved_at"] is None

    def test_final_transition_requires_approved_by_and_approved_at(self, db_session, client):
        case = AuditCase(id="case_spec006_b", name="Caso spec-006 b")
        db_session.add(case)
        db_session.commit()

        created = client.post(
            "/api/findings", json=_finding_payload(case_id=case.id, severity="critical")
        ).json()
        finding_id = created["id"]
        assert created["status"] == "pending_review"

        # Sin approved_by: la transición a final debe rechazarse.
        rejected = client.patch(f"/api/findings/{finding_id}", json={"status": "final"})
        assert rejected.status_code == 400
        assert rejected.json()["code"] == "approval_required"

        # Con approved_by: la transición procede y approved_at se setea server-side.
        approved = client.patch(
            f"/api/findings/{finding_id}",
            json={"status": "final", "approved_by": "auditor-humano-1"},
        )
        assert approved.status_code == 200
        data = approved.json()
        assert data["status"] == "final"
        assert data["approved_by"] == "auditor-humano-1"
        assert data["approved_at"] is not None

    def test_low_severity_finding_can_reach_final_without_approval(self, db_session, client):
        case = AuditCase(id="case_spec006_c", name="Caso spec-006 c")
        db_session.add(case)
        db_session.commit()

        created = client.post(
            "/api/findings", json=_finding_payload(case_id=case.id, severity="low")
        ).json()
        assert created["status"] == "draft"

        response = client.patch(f"/api/findings/{created['id']}", json={"status": "final"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "final"
        assert data["approved_by"] is None

    async def test_chainlit_exposes_approve_reject_action_for_pending_review(self, monkeypatch):
        """`chainlit_ui.chat._maybe_offer_approval_actions` debe ofrecer acciones tipadas
        (`cl.Action` name="approve_finding"/"reject_finding") para un `create_finding` que
        haya producido un hallazgo high/critical en pending_review, y no ofrecer nada para
        uno low/medium en draft. Se mockean `cl.Message`/`cl.Action` porque un `cl.Message`
        real requiere un contexto de sesión Chainlit activo, inexistente en este test unitario.
        """
        from chainlit_ui import chat as chat_module

        sent_messages: list[object] = []

        class _FakeAction:
            def __init__(self, name: str, payload: dict, label: str) -> None:
                self.name = name
                self.payload = payload
                self.label = label

        class _FakeMessage:
            def __init__(self, content: str, actions: list | None = None) -> None:
                self.content = content
                self.actions = actions or []

            async def send(self) -> None:
                sent_messages.append(self)

        monkeypatch.setattr(chat_module.cl, "Message", _FakeMessage)
        monkeypatch.setattr(chat_module.cl, "Action", _FakeAction)

        pending_high = ToolCallRecord(
            tool_name="create_finding",
            tool_input={},
            tool_output={"finding_id": "f-high-1", "severity": "high", "status": "pending_review"},
        )
        final_low = ToolCallRecord(
            tool_name="create_finding",
            tool_input={},
            tool_output={"finding_id": "f-low-1", "severity": "low", "status": "draft"},
        )

        await chat_module._maybe_offer_approval_actions([pending_high, final_low])

        assert len(sent_messages) == 1
        action_names = {action.name for action in sent_messages[0].actions}
        assert action_names == {"approve_finding", "reject_finding"}
        for action in sent_messages[0].actions:
            assert action.payload == {"finding_id": "f-high-1"}

    def test_rejected_finding_preserves_record(self, db_session, client):
        case = AuditCase(id="case_spec006_d", name="Caso spec-006 d")
        db_session.add(case)
        db_session.commit()

        created = client.post(
            "/api/findings", json=_finding_payload(case_id=case.id, severity="high")
        ).json()
        finding_id = created["id"]
        original_created_at = created["created_at"]

        response = client.patch(f"/api/findings/{finding_id}", json={"status": "rejected"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["title"] == created["title"]
        assert data["created_at"] == original_created_at

        # El registro sigue siendo recuperable (nunca se borra, spec-004).
        fetched = client.get(f"/api/findings/{finding_id}")
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "rejected"

        db_session.expire_all()
        persisted = db_session.get(Finding, finding_id)
        assert persisted is not None
        assert persisted.status == "rejected"
