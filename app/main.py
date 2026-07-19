"""FastAPI entrypoint.

    uvicorn app.main:app --reload

Serves the homepage and trust pages, static assets, crawl files (robots/sitemap), and the
JSON API at "/recommend" (docs at "/docs"). Adds request-id logging, a per-IP rate limit,
CORS, response caching, security headers, and an optional Sentry hook, all configured by
environment variables (see app/config.py) with safe defaults. The catalog is loaded once
at startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from . import config, pages
from . import recommend as rec
from .cache import LRUCache
from .models import Feedback, InteractionRule, RecommendationResponse, UserInput
from .normalize import LOCAL_DRUG_CLASSES
from .ratelimit import RateLimiter
from .retrieval import load_corpus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("sleepwise")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'; object-src 'none'"
    ),
}
# Swagger UI loads assets from a CDN, so the strict CSP is not applied to the docs.
_CSP_EXEMPT = {"/docs", "/redoc", "/openapi.json"}

# Trust / content pages served from static HTML.
_PAGES = {
    "/about": "about.html",
    "/methodology": "methodology.html",
    "/privacy": "privacy.html",
    "/sources": "sources.html",
    "/medical-disclaimer": "medical-disclaimer.html",
    "/contact": "contact.html",
    "/editorial-policy": "editorial-policy.html",
    "/terms": "terms.html",
}


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
# The web app is same-origin; cross-origin API access is opt-in via configuration
# rather than a wildcard default.
_cors_origins = config.cors_origins()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

SUPPLEMENTS, RULES = rec.load_catalog()
_CORPUS = load_corpus()
_SUPP_BY_ID = {s.id: s for s in SUPPLEMENTS}
_INTERACTIONS: dict[str, InteractionRule] = {}
for _rule in RULES:
    _INTERACTIONS.setdefault(pages.interaction_slug(_rule), _rule)
_limiter = RateLimiter(config.rate_limit(), config.rate_window())
_cache: LRUCache[str, RecommendationResponse] = LRUCache(maxsize=256)


@app.middleware("http")
async def observe_and_secure(
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
    for key, value in _SECURITY_HEADERS.items():
        if key == "Content-Security-Policy" and request.url.path in _CSP_EXEMPT:
            continue
        response.headers.setdefault(key, value)
    return response


def _page(name: str) -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / name).read_text(encoding="utf-8"))


def _make_page_route(filename: str) -> Callable[[], HTMLResponse]:
    def route() -> HTMLResponse:
        return _page(filename)

    return route


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return _page("index.html")


for _path, _filename in _PAGES.items():
    app.add_api_route(
        _path,
        _make_page_route(_filename),
        methods=["GET"],
        response_class=HTMLResponse,
        include_in_schema=False,
    )


# no-cache means "revalidate before reuse": browsers get cheap 304s day to day but pick
# up new CSS/JS immediately after a deploy instead of running stale cached assets.
_REVALIDATE = {"Cache-Control": "no-cache"}


@app.get("/site.css", include_in_schema=False)
def site_css() -> FileResponse:
    return FileResponse(STATIC_DIR / "site.css", media_type="text/css", headers=_REVALIDATE)


@app.get("/app.js", include_in_schema=False)
def app_js() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "app.js", media_type="application/javascript", headers=_REVALIDATE
    )


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {config.base_url()}/sitemap.xml\n"


@app.get("/.well-known/security.txt", response_class=PlainTextResponse, include_in_schema=False)
def security_txt() -> str:
    return (
        "Contact: https://github.com/kelvinasiedu-programmer/sleepwise/issues\n"
        "Expires: 2027-06-30T00:00:00.000Z\n"
        "Preferred-Languages: en\n"
        f"Canonical: {config.base_url()}/.well-known/security.txt\n"
        "Policy: https://github.com/kelvinasiedu-programmer/sleepwise/blob/main/SECURITY.md\n"
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap() -> Response:
    base = config.base_url()
    paths = [
        "/",
        *_PAGES.keys(),
        "/supplements",
        "/interactions",
        *(f"/supplements/{s.id}" for s in SUPPLEMENTS),
        *(f"/interactions/{slug}" for slug in _INTERACTIONS),
    ]
    urls = "".join(f"<url><loc>{base}{path}</loc></url>" for path in paths)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/supplements", response_class=HTMLResponse, include_in_schema=False)
def supplements_index() -> HTMLResponse:
    return HTMLResponse(
        pages.render_supplement_index(SUPPLEMENTS, f"{config.base_url()}/supplements")
    )


@app.get("/supplements/{supp_id}", response_class=HTMLResponse, include_in_schema=False)
def supplement_page(supp_id: str) -> HTMLResponse:
    supplement = _SUPP_BY_ID.get(supp_id)
    if supplement is None:
        raise HTTPException(status_code=404, detail="Unknown supplement")
    chunks = [c for c in _CORPUS if c.supplement_id == supp_id]
    canonical = f"{config.base_url()}/supplements/{supp_id}"
    return HTMLResponse(pages.render_supplement(supplement, chunks, RULES, canonical))


@app.get("/interactions", response_class=HTMLResponse, include_in_schema=False)
def interactions_index() -> HTMLResponse:
    entries = [
        (slug, f"{_SUPP_BY_ID[rule.supplement_id].name} and {pages.humanize_target(rule)}")
        for slug, rule in sorted(_INTERACTIONS.items())
        if rule.supplement_id in _SUPP_BY_ID
    ]
    return HTMLResponse(
        pages.render_interaction_index(entries, f"{config.base_url()}/interactions")
    )


@app.get("/interactions/{slug}", response_class=HTMLResponse, include_in_schema=False)
def interaction_page(slug: str) -> HTMLResponse:
    rule = _INTERACTIONS.get(slug)
    if rule is None or rule.supplement_id not in _SUPP_BY_ID:
        raise HTTPException(status_code=404, detail="Unknown interaction")
    canonical = f"{config.base_url()}/interactions/{slug}"
    return HTMLResponse(pages.render_interaction(rule, _SUPP_BY_ID[rule.supplement_id], canonical))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "supplements": len(SUPPLEMENTS),
        "rules": len(RULES),
        "engine_version": rec.SAFETY_ENGINE_VERSION,
        "dataset_version": rec.DATASET_VERSION,
    }


@app.get("/api/suggestions", include_in_schema=False)
def api_suggestions() -> dict:
    """Autocomplete lists for the form. Free text still works for anything unlisted."""
    return {
        "medications": sorted({name.title() for name in LOCAL_DRUG_CLASSES}),
        "supplements": [s.name for s in SUPPLEMENTS],
    }


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


@app.post("/feedback")
def feedback_endpoint(feedback: Feedback) -> dict:
    # Logged for product insight only; the free-text note is length-capped and not tied to inputs.
    logger.info("feedback useful=%s note_len=%s", feedback.useful, len(feedback.note or ""))
    return {"ok": True}
