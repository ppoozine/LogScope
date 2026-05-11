"""In-memory per-user rate limiter for /drafts/generate.

Per spec §7.2 — 10 calls per 60 sec per requested_by user. In-memory means
the limit is per worker; multi-worker deployments may exceed it, accepted
trade-off for v1 (Redis-based throttle is v2).
"""
import threading
import time
import uuid
from collections import defaultdict, deque


class ThrottleExceeded(Exception):  # noqa: N818  # public name expected by router & tests
    pass


class InMemoryThrottle:
    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._calls: dict[uuid.UUID, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: uuid.UUID) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._calls[user_id]
            while q and q[0] < now - self._window:
                q.popleft()
            if len(q) >= self._max:
                raise ThrottleExceeded(
                    f"max {self._max} calls per {self._window}s exceeded"
                )
            q.append(now)


_DEFAULT_THROTTLE = InMemoryThrottle(max_calls=10, window_seconds=60)


def get_throttle() -> InMemoryThrottle:
    return _DEFAULT_THROTTLE
