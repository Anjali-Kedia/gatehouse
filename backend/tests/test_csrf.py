"""CSRF protection: double-submit cookie on the three mutating endpoints."""

_READ_PAYLOAD = {
    "user_request": "What's the status of my order 1001?",
    "proposed_action": {"tool": "get_order", "arguments": {"order_ref": "1001"}},
}


def test_first_request_bootstraps_without_csrf_header(client):
    # A brand-new session's very first request can't be a forged request
    # against a pre-existing session — it must succeed with no header at all.
    response = client.post("/evaluations", json=_READ_PAYLOAD)
    assert response.status_code == 201
    assert "gatehouse_csrf" in response.cookies


def test_second_mutating_request_without_csrf_header_is_rejected(client):
    # Bootstraps the session and the CSRF cookie via the fixture's wrapped
    # `.post`, which behaves like a real browser (auto-attaches the header).
    client.post("/evaluations", json=_READ_PAYLOAD)

    # `.request(...)` bypasses that wrapper, proving the *server* enforces
    # this — not just that the test helper happens to always send a header.
    response = client.request("POST", "/evaluations", json=_READ_PAYLOAD)
    assert response.status_code == 403


def test_mutating_request_with_wrong_csrf_header_is_rejected(client):
    client.post("/evaluations", json=_READ_PAYLOAD)

    response = client.request(
        "POST", "/evaluations", json=_READ_PAYLOAD, headers={"X-CSRF-Token": "not-the-real-token"}
    )
    assert response.status_code == 403


def test_correct_csrf_header_is_accepted(client):
    client.post("/evaluations", json=_READ_PAYLOAD)
    csrf_token = client.cookies.get("gatehouse_csrf")

    response = client.request("POST", "/evaluations", json=_READ_PAYLOAD, headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 201


def test_session_that_predates_the_csrf_cookie_self_heals_on_first_write(client):
    """A session cookie can exist without a CSRF cookie yet — e.g. this code
    shipping after visitors already had a session. That first write must
    succeed and mint the cookie, not 403 with no way to ever recover: FastAPI
    discards a dependency's set_cookie calls once any dependency raises, so if
    this path incorrectly required the header here, it would 403 forever.
    """
    response = client.request(
        "POST",
        "/evaluations",
        json=_READ_PAYLOAD,
        headers={"Cookie": "gatehouse_session=some-old-preexisting-session-id"},
    )
    assert response.status_code == 201
    assert "gatehouse_csrf" in response.cookies
