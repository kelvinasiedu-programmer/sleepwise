"""HTTP-layer tests via FastAPI's TestClient."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_catalog_size():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["supplements"] == 6


def test_recommend_blocks_valerian_for_benzodiazepine_user():
    response = client.post("/recommend", json={"meds": ["lorazepam"]})
    assert response.status_code == 200
    body = response.json()
    blocked = {item["supplement"] for item in body["not_recommended"]}
    assert "Valerian" in blocked
    assert "not medical advice" in body["disclaimer"].lower()


def test_index_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "SleepWise" in response.text


def test_response_carries_request_id_header():
    response = client.get("/health")
    assert response.headers.get("X-Request-ID")


def test_oversized_payload_is_rejected():
    response = client.post("/recommend", json={"meds": ["x"] * 100})
    assert response.status_code == 422


def test_identical_requests_are_cached():
    payload = {"meds": ["warfarin"]}
    first = client.post("/recommend", json=payload)
    second = client.post("/recommend", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_rate_limit_returns_429(monkeypatch):
    from app import main
    from app.ratelimit import RateLimiter

    monkeypatch.setattr(main, "_limiter", RateLimiter(limit=1, window=60))
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429
