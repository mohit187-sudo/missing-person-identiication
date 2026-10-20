"""In-memory sliding-window rate limiting (per-process).

Suitable for local demo and single-worker deployments. For horizontal scaling,
swap the store for Redis — the dependency interface is intentionally tiny.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, Request

from backend.app.core.config import settings
from backend.app.core.exceptions import RateLimitError

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)


class RateLimiter:
    def __init__(self, times: int, seconds: int = 60, scope: str = "api"):
        self.times = times
        self.seconds = seconds
        self.scope = scope

    def _key(self, request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            ip = fwd.split(",")[0].strip()
        return f"{self.scope}:{ip}"

    def __call__(self, request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        key = self._key(request)
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > self.seconds:
                q.popleft()
            if len(q) >= self.times:
                retry = int(self.seconds - (now - q[0])) + 1
                raise RateLimitError(retry_after_seconds=retry)
            q.append(now)


def login_rate_limit() -> RateLimiter:
    return RateLimiter(settings.login_rate_limit_per_minute, 60, scope="login")


def api_rate_limit() -> RateLimiter:
    return RateLimiter(settings.api_rate_limit_per_minute, 60, scope="api")


# Convenience dependencies
RequireLoginRate = Depends(login_rate_limit())
RequireApiRate = Depends(api_rate_limit())


def reset_rate_limits() -> None:
    """Test helper."""
    with _lock:
        _hits.clear()
