"""Server-rendered content page tests (supplement and interaction guides)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    from app import main
    from app.ratelimit import RateLimiter

    monkeypatch.setattr(main, "_limiter", RateLimiter(limit=10000, window=60))


def test_supplement_index_lists_all_six():
    response = client.get("/supplements")
    assert response.status_code == 200
    for supplement_id in (
        "melatonin",
        "magnesium",
        "l_theanine",
        "glycine",
        "valerian",
        "ashwagandha",
    ):
        assert f"/supplements/{supplement_id}" in response.text


def test_supplement_page_has_evidence_and_checker_link():
    response = client.get("/supplements/melatonin")
    assert response.status_code == 200
    assert "Melatonin for sleep" in response.text
    assert "ods.od.nih.gov" in response.text  # evidence keeps its citation
    assert "not medical advice" in response.text.lower()


def test_unknown_supplement_returns_404():
    assert client.get("/supplements/creatine").status_code == 404


def test_interaction_index_and_page():
    index = client.get("/interactions")
    assert index.status_code == 200
    assert "/interactions/valerian-and-benzodiazepine" in index.text

    page = client.get("/interactions/valerian-and-benzodiazepine")
    assert page.status_code == 200
    assert "Valerian" in page.text
    assert "clinician" in page.text.lower()
    # Cautious language only: interaction pages never declare a combination safe.
    assert "is safe" not in page.text.lower()


def test_unknown_interaction_returns_404():
    assert client.get("/interactions/melatonin-and-coffee").status_code == 404


def test_sitemap_includes_content_pages():
    sitemap = client.get("/sitemap.xml").text
    assert "/supplements/melatonin" in sitemap
    assert "/interactions/valerian-and-benzodiazepine" in sitemap


def test_security_txt_served():
    response = client.get("/.well-known/security.txt")
    assert response.status_code == 200
    assert "Contact:" in response.text
    assert "Expires:" in response.text


def test_supplement_page_has_truthful_medical_schema():
    text = client.get("/supplements/melatonin").text
    assert "application/ld+json" in text
    assert '"MedicalWebPage"' in text
    assert '"DietarySupplement"' in text
    assert '"lastReviewed"' in text
    # No fabricated reviewer: schema must not claim clinician review that never happened.
    assert "reviewedBy" not in text
    assert '"Physician"' not in text


def test_interaction_page_has_schema_and_provenance():
    text = client.get("/interactions/valerian-and-benzodiazepine").text
    assert '"MedicalWebPage"' in text
    assert '"lastReviewed"' in text
    assert "not yet independently reviewed by a clinician" in text
    assert "reviewedBy" not in text


def test_editorial_policy_page_discloses_review_status():
    text = client.get("/editorial-policy").text
    assert "Editorial policy" in text
    assert "not yet been independently reviewed" in text
