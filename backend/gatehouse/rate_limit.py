"""A small in-memory rate limiter — enough to close the "unbounded real-API-cost
vector on a public demo" gap without pulling in a distributed store. A real
multi-instance deployment would need a shared backend (e.g. Redis) instead;
this only protects a single process, which is what this app actually is.
"""
import threading
import time


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> bool:
        """Returns True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= self._window_seconds:
                window_start, count = now, 0
            if count >= self._max_requests:
                self._windows[key] = (window_start, count)
                return False
            self._windows[key] = (window_start, count + 1)
            return True
