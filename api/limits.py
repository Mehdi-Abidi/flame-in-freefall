"""Sliding-window rate limits for /ask, so a public chat cannot drain the shared LLM quota.

Limits come from environment variables:
    ASK_LIMIT_PER_MINUTE   per visitor, default 6
    ASK_LIMIT_PER_DAY      per visitor, default 60
    ASK_GLOBAL_PER_MINUTE  all visitors together, default 20
    ASK_GLOBAL_PER_DAY     all visitors together, default 400
"""

import math
import os
import threading
import time
from collections import deque
from typing import Callable, Dict, Optional, Tuple

MINUTE = 60.0
DAY = 86400.0
MAX_TRACKED_VISITORS = 10000


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


class RateLimiter:
    def __init__(self, per_minute: int = 6, per_day: int = 60, global_per_minute: int = 20, global_per_day: int = 400,
                 clock: Callable[[], float] = time.monotonic):
        self.rules = {
            "visitor": ((MINUTE, per_minute), (DAY, per_day)),
            "global": ((MINUTE, global_per_minute), (DAY, global_per_day)),
        }
        self.clock = clock
        self.visitors: Dict[str, deque] = {}
        self.everyone: deque = deque()
        self.lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "RateLimiter":
        return cls(_env_int("ASK_LIMIT_PER_MINUTE", 6), _env_int("ASK_LIMIT_PER_DAY", 60),
                   _env_int("ASK_GLOBAL_PER_MINUTE", 20), _env_int("ASK_GLOBAL_PER_DAY", 400))

    @staticmethod
    def _wait(stamps: deque, now: float, window: float, limit: int) -> Optional[float]:
        recent = [t for t in stamps if now - t < window]
        if len(recent) < limit:
            return None
        return window - (now - recent[-limit])

    def check(self, visitor: str) -> Tuple[bool, int, str]:
        """Record one request. Returns (allowed, retry_after_seconds, scope that was exceeded)."""
        with self.lock:
            now = self.clock()
            stamps = self.visitors.get(visitor)
            if stamps is None:
                if len(self.visitors) >= MAX_TRACKED_VISITORS:
                    self._forget_idle(now)
                stamps = self.visitors[visitor] = deque()
            for scope, queue in (("visitor", stamps), ("global", self.everyone)):
                while queue and now - queue[0] >= DAY:
                    queue.popleft()
                for window, limit in self.rules[scope]:
                    wait = self._wait(queue, now, window, limit)
                    if wait is not None:
                        return False, max(1, math.ceil(wait)), scope
            stamps.append(now)
            self.everyone.append(now)
            return True, 0, ""

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, q in self.visitors.items() if not q or now - q[-1] >= MINUTE]:
            del self.visitors[key]
        while len(self.visitors) >= MAX_TRACKED_VISITORS:
            self.visitors.pop(next(iter(self.visitors)))


def visitor_key(forwarded_for: Optional[str], client_host: Optional[str]) -> str:
    """Use the rightmost X-Forwarded-For entry, the one added by the hosting proxy, which a client cannot forge."""
    if forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return client_host or "unknown"
