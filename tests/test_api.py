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
