"""Unit tests for the individual health checks."""

from __future__ import annotations

import asyncio
import socket

import httpx

from ctcv_api.health import check_db, check_qdrant, check_redis, overall_status, run_checks


async def test_check_db_ok_and_error(engine, settings_factory):
    assert await check_db(engine) == "ok"
    from ctcv_api.db import make_engine

    broken = make_engine("sqlite+pysqlite:///Z:/definitely/missing/dir/x.db")
    try:
        assert await check_db(broken) == "error"
    finally:
        broken.dispose()


async def test_check_redis_skipped_when_unset():
    assert await check_redis(None, 0.5) == "skipped"
    assert await check_redis("", 0.5) == "skipped"


async def test_check_redis_ok_against_listening_socket():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        assert await check_redis(f"redis://127.0.0.1:{port}/0", 1.0) == "ok"
    finally:
        server.close()
        await server.wait_closed()


async def test_check_redis_error_when_nothing_listens():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert await check_redis(f"redis://127.0.0.1:{port}/0", 1.0) == "error"


async def test_check_qdrant_skipped_when_unset():
    assert await check_qdrant(None, 0.5) == "skipped"


async def test_check_qdrant_ok_error_and_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/healthz"
        return httpx.Response(200 if "good" in request.url.host else 503)

    transport = httpx.MockTransport(handler)
    assert await check_qdrant("http://good:6333/", 0.5, transport) == "ok"
    assert await check_qdrant("http://bad:6333", 0.5, transport) == "error"

    def explode(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert await check_qdrant("http://down:6333", 0.5, httpx.MockTransport(explode)) == "error"


async def test_run_checks_shape(engine, settings):
    checks = await run_checks(settings, engine)
    assert checks == {"db": "ok", "redis": "skipped", "qdrant": "skipped"}


def test_overall_status():
    assert overall_status({"db": "ok", "redis": "skipped", "qdrant": "skipped"}) == "ok"
    assert overall_status({"db": "ok", "redis": "error", "qdrant": "skipped"}) == "degraded"
