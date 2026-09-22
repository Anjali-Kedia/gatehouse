"""Integration tests for duplicate execution and idempotency-key conflicts,
run against the real FastAPI app (mock Jev adapter, isolated per-test DB).
"""


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


def test_duplicate_execute_causes_one_ledger_mutation(client):
    evaluation = _propose_refund(client, amount_cents=4000)
    assert evaluation["decision"] == "REVIEW"

    approve = client.post(f"/evaluations/{evaluation['id']}/approve")
    assert approve.status_code == 200

    first = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert first.status_code == 200
    assert first.json()["replayed"] is False
    assert first.json()["result"]["remaining_balance_cents"] == 8900 - 4000

    # Same evaluation, no explicit idempotency_key -> defaults to the same key both
    # times, simulating a client retrying an identical request.
    second = client.post(f"/evaluations/{evaluation['id']}/execute", json={})
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["result"] == first.json()["result"]

    # Prove it at the ledger, not just the response: a fresh read shows only one
    # refund was ever applied, not two.
    check = client.post(
        "/evaluations",
        json={
            "user_request": "What's the status of my order 1001?",
            "proposed_action": {"tool": "get_order", "arguments": {"order_ref": "1001"}},
        },
    ).json()
    assert check["hard_rule_result"]["data"]["remaining_balance_cents"] == 8900 - 4000


def test_idempotency_key_reused_with_different_action_is_a_conflict(client):
    first_evaluation = _propose_refund(client, amount_cents=1000)
    client.post(f"/evaluations/{first_evaluation['id']}/approve")
    first_exec = client.post(f"/evaluations/{first_evaluation['id']}/execute", json={})
    assert first_exec.status_code == 200

    second_evaluation = _propose_refund(client, amount_cents=2000)
    client.post(f"/evaluations/{second_evaluation['id']}/approve")

    conflict = client.post(
        f"/evaluations/{second_evaluation['id']}/execute",
        json={"idempotency_key": first_evaluation["id"]},  # collides with the first evaluation's default key
    )
    assert conflict.status_code == 409
    assert "IDEMPOTENCY_CONFLICT" in conflict.json()["detail"]["reason_codes"]


def test_changing_arguments_invalidates_the_prior_approval(client):
    original = _propose_refund(client, amount_cents=4000)
    client.post(f"/evaluations/{original['id']}/approve")

    # Same order, different amount -> different action_hash -> a genuinely
    # different action, not covered by the approval granted for `original`.
    changed = _propose_refund(client, amount_cents=5000)
    assert changed["action_hash"] != original["action_hash"]

    exec_resp = client.post(f"/evaluations/{changed['id']}/execute", json={})
    assert exec_resp.status_code == 403
    assert "APPROVAL_NOT_FOUND" in exec_resp.json()["detail"]["reason_codes"]
