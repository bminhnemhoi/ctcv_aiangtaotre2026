"""Prometheus metrics: a per-app registry, an ASGI middleware and the ``/metrics`` body.

Each application gets its own ``CollectorRegistry`` so ``create_app()`` can be
called many times (tests) without duplicate-collector errors. The path label is
the matched route template (``/v1/scenarios``), never the raw URL, to keep
cardinality bounded and to avoid leaking ids into metrics.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client import generate_latest as _generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("ctcv_api.access")

UNMATCHED_PATH = "unmatched"
SERVER_ERROR_STATUS = 500


@dataclass(frozen=True, slots=True)
class HttpMetrics:
    """Registry plus the two HTTP collectors every CTCV service exposes."""

    registry: CollectorRegistry
    requests_total: Counter
    request_seconds: Histogram


def build_metrics() -> HttpMetrics:
    """Create an isolated registry with ``http_requests_total`` and a latency histogram."""
    registry = CollectorRegistry()
    requests_total = Counter(
        "http_requests_total",
        "HTTP requests by method, route template and status code",
        ["method", "path", "status"],
        registry=registry,
    )
    request_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency by method and route template",
        ["method", "path"],
        registry=registry,
    )
    return HttpMetrics(registry, requests_total, request_seconds)


def render(metrics: HttpMetrics) -> tuple[bytes, str]:
    """Return the Prometheus exposition body and its content type."""
    return _generate_latest(metrics.registry), CONTENT_TYPE_LATEST


@lru_cache(maxsize=256)
def _tail_regex(pattern: str) -> re.Pattern[str]:
    """Compile a route regex so it can match the tail of a longer (prefixed) path."""
    return re.compile(pattern.removeprefix("^"))


def route_template(scope: Scope) -> str:
    """The matched route's full path template, or ``unmatched`` for 404s.

    Routers included with a prefix keep their local ``path_format`` (``/health``, not
    ``/v1/health``); the prefix is recovered by matching the route regex against the
    tail of the request path (minus ``root_path``) and prepending what comes before.
    """
    route = scope.get("route")
    template = getattr(route, "path_format", None)
    if not isinstance(template, str):
        return UNMATCHED_PATH
    path, root = str(scope.get("path", "")), str(scope.get("root_path", ""))
    if root and path.startswith(root):
        path = path[len(root) :]
    regex = getattr(route, "path_regex", None)
    match = _tail_regex(regex.pattern).search(path) if regex is not None else None
    return path[: match.start()] + template if match else template


class MetricsMiddleware:
    """Count and time every HTTP request; emit one JSON access-log line per request."""

    def __init__(self, app: ASGIApp, metrics: HttpMetrics) -> None:
        """Wrap ``app`` and record into ``metrics``."""
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Observe one request; a crash downstream is recorded as 500 and re-raised."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = SERVER_ERROR_STATUS

        async def send_and_capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_and_capture)
        finally:
            self._record(scope, status, time.perf_counter() - started)

    def _record(self, scope: Scope, status: int, elapsed: float) -> None:
        method = str(scope.get("method", "GET"))
        path = route_template(scope)
        self.metrics.requests_total.labels(method, path, str(status)).inc()
        self.metrics.request_seconds.labels(method, path).observe(elapsed)
        log.info(
            "request",
            extra={"method": method, "path": path, "status": status, "ms": round(elapsed * 1e3, 1)},
        )
