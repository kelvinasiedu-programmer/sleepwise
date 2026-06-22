"""Runtime configuration via environment variables.

Every feature degrades gracefully: with nothing set, SleepWise uses BM25 retrieval and
the deterministic explanation template — fully functional, zero keys, zero cost. Set the
variables below to upgrade.

  SLEEPWISE_RETRIEVER        "bm25" (default) | "embedding"
  OPENAI_API_KEY             enables the embedding retriever (with RETRIEVER=embedding)
  SLEEPWISE_EMBEDDING_MODEL  default "text-embedding-3-small"
  ANTHROPIC_API_KEY          enables the LLM explanation layer
  SLEEPWISE_LLM_MODEL        default "claude-haiku-4-5"

Values are read at call time so they can be toggled per-process (and per-test).
"""

from __future__ import annotations

import os


def retriever_kind() -> str:
    return os.getenv("SLEEPWISE_RETRIEVER", "bm25").lower()


def openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def embedding_model() -> str:
    return os.getenv("SLEEPWISE_EMBEDDING_MODEL", "text-embedding-3-small")


def anthropic_api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY")


def llm_model() -> str:
    return os.getenv("SLEEPWISE_LLM_MODEL", "claude-haiku-4-5")


def llm_enabled() -> bool:
    return bool(anthropic_api_key())


def embeddings_enabled() -> bool:
    return retriever_kind() == "embedding" and bool(openai_api_key())


def cors_origins() -> list[str]:
    raw = os.getenv("SLEEPWISE_CORS_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def rate_limit() -> int:
    return int(os.getenv("SLEEPWISE_RATE_LIMIT", "60"))


def rate_window() -> float:
    return float(os.getenv("SLEEPWISE_RATE_WINDOW", "60"))


def sentry_dsn() -> str | None:
    return os.getenv("SENTRY_DSN")
