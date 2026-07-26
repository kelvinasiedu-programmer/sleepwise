"""HTTP-layer tests via FastAPI's TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    """Give each test a generous rate limiter so requests don't bleed across tests."""
    from app import main
    from app.ratelimit import RateLimiter

    monkeypatch.setattr(main, "_limiter", RateLimiter(limit=10000, window=60))


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


def test_homepage_has_seo_and_hero():
    response = client.get("/")
    assert response.status_code == 200
    assert "Check sleep supplements" in response.text
    assert 'name="description"' in response.text


def test_scenarios_endpoint_serves_fixed_profiles():
    body = client.get("/api/scenarios").json()
    ids = {s["id"] for s in body["scenarios"]}
    # The set must keep covering the interesting engine paths.
    assert {"blood-thinner", "benzodiazepine", "hard-gate", "kidney", "ambiguous", "none"} <= ids
    for scenario in body["scenarios"]:
        assert scenario["label"] and scenario["description"]
        assert set(scenario["profile"]) == {"goal", "meds", "conditions", "current_supplements"}


def test_homepage_has_no_free_text_health_input():
    # The demonstration framing is structural: there is nowhere to type your own
    # medications, so the page cannot be used for personal guidance.
    text = client.get("/").text
    assert 'id="meds"' not in text
    assert 'id="supps"' not in text
    assert 'type="checkbox"' not in text
    assert 'id="scenarios"' in text
    assert "engineering demonstration on sample data" in text


def test_every_scenario_runs_through_the_engine():
    for scenario in client.get("/api/scenarios").json()["scenarios"]:
        response = client.post("/recommend", json=scenario["profile"])
        assert response.status_code == 200, scenario["id"]
        body = response.json()
        items = body["recommended"] + body["not_recommended"]
        assert items, scenario["id"]
        # Commerce stays off for every scenario.
        assert all(item["buy_link"] is None for item in items), scenario["id"]


def test_trust_pages_are_served():
    for path in (
        "/about",
        "/methodology",
        "/privacy",
        "/sources",
        "/medical-disclaimer",
        "/contact",
        "/editorial-policy",
        "/terms",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "SleepWise" in response.text


def test_static_assets_are_served():
    assert client.get("/site.css").status_code == 200
    assert client.get("/app.js").status_code == 200
    favicon = client.get("/favicon.svg")
    assert favicon.status_code == 200
    assert "svg" in favicon.headers["content-type"]
    assert client.get("/favicon.ico").status_code == 200


def test_robots_and_sitemap():
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text


def test_security_headers_present():
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in headers


def test_suggestions_endpoint_lists_meds_and_supplements():
    response = client.get("/api/suggestions")
    assert response.status_code == 200
    body = response.json()
    assert "Xanax" in body["medications"]
    assert "Warfarin" in body["medications"]
    assert "Melatonin" in body["supplements"]


def test_feedback_accepts_valid_and_rejects_invalid():
    assert client.post("/feedback", json={"useful": "yes"}).json() == {"ok": True}
    assert client.post("/feedback", json={"useful": "maybe"}).status_code == 422
