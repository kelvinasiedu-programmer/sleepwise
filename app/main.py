"""FastAPI entrypoint.

    uvicorn app.main:app --reload

Serves a minimal UI at "/" and the JSON API at "/recommend" (docs at "/docs").
The catalog is loaded once at startup.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import recommend as rec
from .models import RecommendationResponse, UserInput

app = FastAPI(
    title="SleepWise",
    description="Safety-first supplement guidance for sleep. Educational, not medical advice.",
    version="0.1.0",
)

SUPPLEMENTS, RULES = rec.load_catalog()
_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "supplements": len(SUPPLEMENTS), "rules": len(RULES)}


@app.post("/recommend", response_model=RecommendationResponse)
def recommend_endpoint(user: UserInput) -> RecommendationResponse:
    return rec.recommend(user, SUPPLEMENTS, RULES)
