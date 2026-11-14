"""A small in-process sliding-window limiter, per key (for example client IP + route).

Single-instance only: with several API servers each keeps its own counts. Move the counters to
Postgres or Redis before running more than one instance (see docs/backend-plan.md, open decision 5).
Per-identifier limits (OTP requests, password failures) are NOT here: they are stored in the database."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int, *, now: float | None = None) -> None:
        t = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and hits[0] <= t - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimited("Too many requests. Please wait a while and try again.")
        hits.append(t)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()
