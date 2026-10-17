"""Sliding-window rate limiter (single process, in memory)."""
from __future__ import annotations

import time
from collections import deque
from typing import Callable


class RateLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.per_minute = per_minute
        self.clock = clock
        self._hits: deque[float] = deque()

    def check(self) -> float:
        """Return 0 if allowed, else seconds until a slot frees up."""
        if self.per_minute <= 0:
            return 0.0
        now = self.clock()
        while self._hits and now - self._hits[0] >= 60:
            self._hits.popleft()
        if len(self._hits) >= self.per_minute:
            return max(0.1, 60 - (now - self._hits[0]))
        self._hits.append(now)
        return 0.0
