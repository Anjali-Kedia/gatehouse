"""Integration test for the per-session rate limit on POST /evaluations."""
from gatehouse.rate_limit import RateLimiter


def test_rate_limit_blocks_excessive_evaluations(client, monkeypatch):
    import api.routers.evaluations as evaluations_router

    monkeypatch.setattr(evaluations_router, "_evaluation_rate_limiter", RateLimiter(max_requests=2, window_seconds=60))

    payload = {
        "user_request": "What's the status of my order 1001?",
        "proposed_action": {"tool": "get_order", "arguments": {"order_ref": "1001"}},
    }

    first = client.post("/evaluations", json=payload)
    second = client.post("/evaluations", json=payload)
    third = client.post("/evaluations", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429
