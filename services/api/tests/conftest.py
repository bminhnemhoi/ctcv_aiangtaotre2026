"""Shared fixtures for ctcv-api tests: isolated settings, app, TestClient, token minting.

Unit tests never load the real TTHC knowledge base: the ``app`` fixture presets both
knowledge services with :class:`OfflineKnowledge` (every call → 503 ``KB_NOT_READY``); a test
that needs answers replaces them with a fake (``app.state.answer_service = ...``).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ctcv_agent.contracts import AskResult, IntakeRequest, IntakeResult
from ctcv_agent.rag.types import KnowledgeBaseNotReady, ProcedureRecord
from ctcv_agent.schemas import SessionContext
from ctcv_agent.tools.backends import set_default_backends
from ctcv_api.auth import create_token
from ctcv_api.db import make_engine, make_session_factory
from ctcv_api.enums import Role
from ctcv_api.main import create_app
from ctcv_api.models import Base
from ctcv_api.settings import Settings
from ctcv_core.config import clear_config_cache, find_repo_root

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCENARIOS_FIXTURES = FIXTURES_DIR / "scenarios"
# Procedure records shared with the agent tests (ADR-007 C2); read-only here.
TTHC_RECORDS_DIR = (
    find_repo_root() / "services" / "agent" / "tests" / "fixtures" / "tthc" / "records"
)
TEST_SECRET = "test-secret-not-for-production-32b+"
ENV_NAMES = (
    "CTCV_ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "QDRANT_URL",
    "JWT_SECRET",
    "JWT_TTL_MINUTES",
    "RATE_LIMIT_PER_MIN",
    "MAX_CONCURRENT_SESSIONS",
    "SCREEN_TTL_SECONDS",
    "LOG_RETENTION_DAYS",
    "CORS_ORIGINS",
    "APP_DOMAIN",
    "SCENARIOS_DIR",
    "API_PORT",
    "API_HOST",
    "LOG_LEVEL",
    "CTCV_DEMO_QR_TOKEN",
    "CTCV_DEMO_STAFF_PASSWORD",
    "CTCV_OLLAMA_BASE_URL",
    "CTCV_RAG_COMPOSE_MODE",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip every variable Settings/RagSettings read so a developer's shell cannot leak in."""
    for name in ENV_NAMES:
        if name in os.environ:
            monkeypatch.delenv(name, raising=False)
    clear_config_cache()
    yield
    clear_config_cache()
    set_default_backends(None)


class OfflineKnowledge:
    """Default knowledge services of the unit-test app: the KB is never read from disk."""

    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        raise KnowledgeBaseNotReady("unit_test")

    def check(self, req: IntakeRequest) -> IntakeResult:
        raise KnowledgeBaseNotReady("unit_test")


class FakeAnswerService:
    """``AnswerService`` returning a fixed result (or raising) and recording every call."""

    def __init__(self, result: AskResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, SessionContext]] = []

    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        self.calls.append((question, ctx))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeIntakeService:
    """``IntakeService`` returning a fixed result (or raising) and recording every request."""

    def __init__(self, result: IntakeResult | Exception) -> None:
        self.result = result
        self.calls: list[IntakeRequest] = []

    def check(self, req: IntakeRequest) -> IntakeResult:
        self.calls.append(req)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture(scope="session")
def tthc_records() -> dict[str, ProcedureRecord]:
    """The three fixture procedures keyed by ``procedure_id``."""
    records = [ProcedureRecord.load(path) for path in sorted(TTHC_RECORDS_DIR.glob("*.json"))]
    return {record.procedure_id: record for record in records}


@pytest.fixture
def fake_answer_service() -> type[FakeAnswerService]:
    return FakeAnswerService


@pytest.fixture
def fake_intake_service() -> type[FakeIntakeService]:
    return FakeIntakeService


@pytest.fixture
def settings_factory() -> Callable[..., Settings]:
    def _make(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "database_url": "sqlite+pysqlite://",
            "jwt_secret": TEST_SECRET,
            "jwt_ttl_minutes": 5,
            "ctcv_env": "test",
            "scenarios_dir": SCENARIOS_FIXTURES,
            "log_level": "WARNING",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return _make


@pytest.fixture
def settings(settings_factory: Callable[..., Settings]) -> Settings:
    return settings_factory()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    application.state.answer_service = OfflineKnowledge()
    application.state.intake_service = OfflineKnowledge()
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_token(settings: Settings) -> Callable[..., str]:
    def _make(role: Role | str, user_id: str | None = None) -> str:
        return create_token(user_id or str(uuid.uuid4()), role, settings)

    return _make


@pytest.fixture
def auth_headers(make_token: Callable[..., str]) -> Callable[[Role | str], dict[str, str]]:
    def _headers(role: Role | str) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(role)}"}

    return _headers


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = make_engine("sqlite+pysqlite://")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    session = make_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
