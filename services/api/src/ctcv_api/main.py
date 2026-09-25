"""FastAPI application factory for the CTCV API.

``create_app(settings)`` wires JSON logging (``ctcv_core.logging``), the database
engine, Prometheus metrics, the request-id and CORS middleware, the unified error
handlers and every router under ``/v1`` (plus ``/health`` and ``/metrics`` at the
root). Run it with ``uv run ctcv-api`` or
``uvicorn ctcv_api.main:create_app --factory``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ctcv_api import get_version
from ctcv_api.db import make_engine, make_session_factory
from ctcv_api.handlers import install_exception_handlers
from ctcv_api.metrics import MetricsMiddleware, build_metrics
from ctcv_api.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from ctcv_api.routers import V1_ROUTERS, system
from ctcv_api.settings import Settings, get_settings
from ctcv_core.logging import setup_logging

API_PREFIX = "/v1"
SERVICE_NAME = "api"
TITLE = "CTCV API"
DESCRIPTION = (
    "Cầm Tay Chỉ Việc — API cho người dân, tình nguyện viên và cán bộ. "
    "Hợp đồng: docs/plan.md §5, docs/decisions/E01-brief.md §3."
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Dispose the engine when the server stops."""
    yield
    app.state.engine.dispose()


def mount_routers(app: FastAPI) -> None:
    """Mount every router under ``/v1`` and alias ``/health``/``/metrics`` at the root."""
    v1 = APIRouter(prefix=API_PREFIX)
    for router in V1_ROUTERS:
        v1.include_router(router)
    app.include_router(v1)
    app.include_router(system.router, include_in_schema=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully wired application for ``settings`` (default: environment)."""
    settings = settings or get_settings()
    setup_logging(SERVICE_NAME, level=settings.log_level)
    app = FastAPI(
        title=TITLE,
        version=get_version(),
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.state.metrics = build_metrics()

    install_exception_handlers(app)
    mount_routers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(MetricsMiddleware, metrics=app.state.metrics)
    app.add_middleware(RequestIdMiddleware)  # outermost: request_id visible to all logs
    return app


def run() -> None:
    """Console entry point (``uv run ctcv-api``): serve with uvicorn on the configured port."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "ctcv_api.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )
