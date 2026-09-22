"""Integration tests for approval expiry and state changing between evaluation
and execution — run against the real FastAPI app (mock Jev adapter, isolated
per-test DB).
"""
from datetime import timedelta

from sqlmodel import Session, select

from gatehouse.models import Approval, Order


def _propose_refund(client, order_ref="1001", amount_cents=4000):
    return client.post(
        "/evaluations",
        json={
            "user_request": f"Please issue a refund for order {order_ref}, I paid for it.",
            "proposed_action": {
                "tool": "issue_refund",
                "arguments": {"order_ref": order_ref, "amount_cents": amount_cents},
            },
        },
    ).json()


def test_expired_approval_is_rejected_and_marked_expired(client, test_engine):
    evaluation = _propose_refund(client)
    approve = client.post(f"/evaluations/{evaluation['id']}/approve").json()

    # Simulate time passing rather than sleeping in a test.
    with Session(test_engine) as session:
        approval = session.get(Approval, approve["id"])
        approval.expires_at = approval.created_at - timedelta(minutes=1)
        session.add(approval)
        session.commit()

    exec_resp = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert exec_resp.status_code == 409
    assert "APPROVAL_EXPIRED" in exec_resp.json()["detail"]["reason_codes"]

    with Session(test_engine) as session:
        approval = session.get(Approval, approve["id"])
        assert approval.status == "expired"


def test_state_changed_since_evaluation_blocks_execute(client, test_engine):
    evaluation = _propose_refund(client, amount_cents=8900)  # the full balance
    client.post(f"/evaluations/{evaluation['id']}/approve")

    # Something else consumed the balance between evaluation and execution.
    with Session(test_engine) as session:
        order = session.exec(select(Order).where(Order.order_ref == "1001")).one()
        order.refunded_amount_cents = order.total_amount_cents
        session.add(order)
        session.commit()

    exec_resp = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert exec_resp.status_code == 409
    reason_codes = exec_resp.json()["detail"]["reason_codes"]
    assert "STATE_CHANGED_SINCE_EVALUATION" in reason_codes
    assert "ALREADY_REFUNDED" in reason_codes


def test_execute_requires_approval_even_for_review_via_jev_unavailable(client, monkeypatch):
    import api.routers.evaluations as evaluations_router
    from gatehouse.jev.base import JevUnavailable
    from gatehouse.reason_codes import ReasonCode

    class _AlwaysUnavailable:
        def evaluate(self, **kwargs):
            raise JevUnavailable(ReasonCode.JEV_UNAVAILABLE, "simulated timeout")

    # Patch the name as the router looked it up (`from gatehouse.jev import
    # get_jev_adapter`) — patching gatehouse.jev's attribute wouldn't affect
    # the router's already-bound reference to the original function.
    monkeypatch.setattr(evaluations_router, "get_jev_adapter", lambda: _AlwaysUnavailable())

    evaluation = client.post(
        "/evaluations",
        json={
            "user_request": "What's the status of my order 1001?",
            "proposed_action": {"tool": "get_order", "arguments": {"order_ref": "1001"}},
        },
    ).json()
    assert evaluation["decision"] == "REVIEW"
    assert "JEV_UNAVAILABLE" in evaluation["reason_codes"]

    # No execution should happen without a human approving first — including
    # reads, when the reason for REVIEW was Jev being unavailable.
    exec_resp = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert exec_resp.status_code == 403
    assert "APPROVAL_NOT_FOUND" in exec_resp.json()["detail"]["reason_codes"]

    client.post(f"/evaluations/{evaluation['id']}/approve")
    exec_resp = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert exec_resp.status_code == 200
