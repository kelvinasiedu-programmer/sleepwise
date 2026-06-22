"""A tiny in-memory, fixed-window rate limiter (per key).

Sufficient for a single free-tier instance. For multi-instance deployments this would
move to a shared store (e.g. Redis) — the interface would stay the same.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        """Return True if ``key`` is under its request budget for the current window."""
        moment = time.monotonic() if now is None else now
        hits = self._hits[key]
        cutoff = moment - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(moment)
        return True
