"""Rate limiter — limite le nombre de requêtes/minute (token bucket simple)."""

from __future__ import annotations

import threading
import time
from collections import deque

from .logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket — limite à N requêtes par fenêtre glissante de 60s."""

    def __init__(self, max_requests_per_minute: int):
        self.max_per_minute = max_requests_per_minute
        self.window_seconds = 60.0
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Bloque jusqu'à ce qu'un slot soit disponible."""
        while True:
            with self._lock:
                now = time.monotonic()
                # Purge les timestamps trop vieux
                while self._timestamps and (now - self._timestamps[0]) > self.window_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_per_minute:
                    self._timestamps.append(now)
                    return

                # Attente jusqu'à libération d'un slot
                oldest = self._timestamps[0]
                wait_seconds = (oldest + self.window_seconds) - now

            if wait_seconds > 0:
                logger.debug("Rate limit atteint, attente de %.2fs", wait_seconds)
                time.sleep(wait_seconds + 0.05)
