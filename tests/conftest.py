"""Shared test fixtures.

`hermetic_env` runs automatically and clears every optional integration variable, so the
suite always exercises the offline defaults (BM25 retrieval + the deterministic
explanation template) — never the network — regardless of the developer's shell.
"""

import pytest

_OPTIONAL_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "SLEEPWISE_RETRIEVER",
    "SLEEPWISE_LLM_MODEL",
    "SLEEPWISE_EMBEDDING_MODEL",
    "SENTRY_DSN",
    "SLEEPWISE_CORS_ORIGINS",
    "SLEEPWISE_RATE_LIMIT",
    "SLEEPWISE_RATE_WINDOW",
)


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    for var in _OPTIONAL_VARS:
        monkeypatch.delenv(var, raising=False)
