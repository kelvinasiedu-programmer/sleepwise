"""A latency guard, not a load test.

The real measurements live in `scripts/loadtest.py` and `docs/PERFORMANCE.md`. Load
testing in CI is noisy - shared runners, unpredictable neighbours - so asserting a
throughput figure there would produce flaky failures and train everyone to ignore them.

What is worth guarding in CI is a catastrophic regression: something that turns a 13 ms
request into a multi-second one, such as accidentally loading the model or re-reading the
corpus per request. The budgets below are deliberately loose for that reason. They are
tripwires, not targets.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import RateLimiter

client = TestClient(app)

# Roughly 50x the measured local p50, so ordinary CI-runner noise cannot trip it.
BUDGET_MS = 750.0


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_limiter", RateLimiter(limit=100000, window=60))


def _timed(call) -> float:
    call()  # warm-up: first call pays lazy imports and model load
    started = time.perf_counter()
    response = call()
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200
    return elapsed


def test_recommend_stays_within_budget():
    elapsed = _timed(lambda: client.post("/recommend", json={"meds": ["warfarin"]}))
    assert elapsed < BUDGET_MS, f"/recommend took {elapsed:.0f}ms"


def test_symptoms_stays_within_budget():
    elapsed = _timed(
        lambda: client.post("/symptoms", json={"answers": {"loud-snoring": "applies"}})
    )
    assert elapsed < BUDGET_MS, f"/symptoms took {elapsed:.0f}ms"


def test_content_page_stays_within_budget():
    elapsed = _timed(lambda: client.get("/supplements/melatonin"))
    assert elapsed < BUDGET_MS, f"content page took {elapsed:.0f}ms"


def test_normalizer_model_is_loaded_once_not_per_request():
    """The exported model is ~500 KB of JSON. Parsing it per request would be the most
    likely source of a large latency regression, so pin the caching down."""
    from app.normalizer_model import load_model

    first = load_model()
    assert first is not None
    assert load_model() is first, "model should be cached, not re-parsed"
