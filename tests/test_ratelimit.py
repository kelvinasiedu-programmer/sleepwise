"""Rate limiter tests (deterministic via an injected clock)."""

from app.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=2, window=60)
    assert limiter.allow("ip", now=0) is True
    assert limiter.allow("ip", now=1) is True
    assert limiter.allow("ip", now=2) is False


def test_window_resets_after_it_passes():
    limiter = RateLimiter(limit=1, window=60)
    assert limiter.allow("ip", now=0) is True
    assert limiter.allow("ip", now=30) is False
    assert limiter.allow("ip", now=61) is True


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window=60)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("b", now=0) is True
