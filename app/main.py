"""FastAPI entrypoint.

    uvicorn app.main:app --reload

Serves a minimal UI at "/" and the JSON API at "/recommend" (docs at "/docs").
Adds request-id logging, a per-IP rate limit, CORS, response caching, and an optional
Sentry hook - all configured by environment variables (see app/config.py), all with safe
defaults. The catalog is loaded once at startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from . import config
from . import recommend as rec
from .cache import LRUCache
from .models import RecommendationResponse, UserInput
from .ratelimit import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("sleepwise")


def _init_sentry() -> None:
    dsn = config.sentry_dsn()
    if not dsn:
        return
    try:  # pragma: no cover - optional integration, only with a real DSN
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)
        logger.info("Sentry initialized")
    except ImportError:  # pragma: no cover
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed")


_init_sentry()

app = FastAPI(
    title="SleepWise",
    description="Safety-first supplement guidance for sleep. Educational, not medical advice.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SUPPLEMENTS, RULES = rec.load_catalog()
_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"
_limiter = RateLimiter(config.rate_limit(), config.rate_window())
_cache: LRUCache[str, RecommendationResponse] = LRUCache(maxsize=256)


@app.middleware("http")
async def observe_and_limit(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    client = request.client.host if request.client else "unknown"
    start = time.perf_counter()

    if not _limiter.allow(client):
        logger.warning("rate_limited id=%s client=%s", request_id, client)
        response: Response = JSONResponse(
            {"detail": "Rate limit exceeded. Please try again shortly."}, status_code=429
        )
    else:
        response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request id=%s method=%s path=%s status=%s dur_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "supplements": len(SUPPLEMENTS), "rules": len(RULES)}


def _cache_key(user: UserInput) -> str:
    payload = {
        "goal": user.goal,
        "meds": sorted(m.lower() for m in user.meds),
        "conditions": sorted(c.lower() for c in user.conditions),
        "supplements": sorted(s.lower() for s in user.current_supplements),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@app.post("/recommend", response_model=RecommendationResponse)
def recommend_endpoint(user: UserInput) -> RecommendationResponse:
    key = _cache_key(user)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    result = rec.recommend(user, SUPPLEMENTS, RULES)
    _cache.put(key, result)
    return result
