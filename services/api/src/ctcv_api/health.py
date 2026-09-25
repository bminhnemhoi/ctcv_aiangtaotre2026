"""Health checks for ``/health``: database, Redis and Qdrant.

A dependency that is not configured reports ``skipped`` (brief §3); a configured
one reports ``ok`` or ``error``. Redis is probed with a plain TCP connect (no
client library is needed in E01) and Qdrant through its ``/healthz`` endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Literal
from urllib.parse import urlsplit

import httpx
from sqlalchemy.engine import Engine

from ctcv_api.db import ping
from ctcv_api.settings import Settings

CheckStatus = Literal["ok", "error", "skipped"]
DEFAULT_REDIS_PORT = 6379
QDRANT_HEALTH_PATH = "/healthz"


async def check_db(engine: Engine) -> CheckStatus:
    """``SELECT 1`` through the application engine (in a worker thread)."""
    return "ok" if await asyncio.to_thread(ping, engine) else "error"


async def check_redis(url: str | None, timeout_s: float) -> CheckStatus:
    """TCP-connect to the Redis host/port from ``url``; ``skipped`` when not configured."""
    if not url:
        return "skipped"
    parts = urlsplit(url)
    host, port = parts.hostname or "localhost", parts.port or DEFAULT_REDIS_PORT
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout_s)
    except (OSError, TimeoutError):
        return "error"
    writer.close()
    return "ok"


async def check_qdrant(
    url: str | None,
    timeout_s: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CheckStatus:
    """GET ``/healthz`` on Qdrant; ``skipped`` when not configured."""
    if not url:
        return "skipped"
    target = url.rstrip("/") + QDRANT_HEALTH_PATH
    try:
        async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as client:
            response = await client.get(target)
    except httpx.HTTPError:
        return "error"
    return "ok" if response.is_success else "error"


async def run_checks(settings: Settings, engine: Engine) -> dict[str, CheckStatus]:
    """Run every check concurrently and return ``{db, redis, qdrant}``."""
    db, redis, qdrant = await asyncio.gather(
        check_db(engine),
        check_redis(settings.redis_url, settings.health_timeout_s),
        check_qdrant(settings.qdrant_url, settings.health_timeout_s),
    )
    return {"db": db, "redis": redis, "qdrant": qdrant}


def overall_status(checks: dict[str, CheckStatus]) -> Literal["ok", "degraded"]:
    """``ok`` unless at least one check reports ``error``."""
    return "degraded" if "error" in checks.values() else "ok"
