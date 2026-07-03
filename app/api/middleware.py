import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

MAX_IPS = 10000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self._requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - 60

        if now - self._last_cleanup > 60:
            self._cleanup(cutoff)
            self._last_cleanup = now

        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]

        if len(self._requests[client_ip]) >= self._requests_per_minute:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        self._requests[client_ip].append(now)
        result: Response = await call_next(request)
        return result

    def _cleanup(self, cutoff: float) -> None:
        """Remove stale entries and enforce IP limit.

        Eviction strategy:
        1. Remove IPs with no recent requests (older than cutoff)
        2. If still over MAX_IPS, remove oldest entries first
        """
        empty_keys = [ip for ip, times in self._requests.items() if not times or times[-1] < cutoff]
        for ip in empty_keys:
            del self._requests[ip]

        if len(self._requests) > MAX_IPS:
            sorted_ips = sorted(self._requests.items(), key=lambda x: x[1][-1] if x[1] else 0)
            for ip, _ in sorted_ips[: len(sorted_ips) - MAX_IPS]:
                del self._requests[ip]
