"""Invariant 2 at the API edge: a citizen question is never logged nor stored.

``POST /v1/coach/ask`` receives free text that may contain personal data. Whatever the
outcome (answer, 503, crash, 422), the question text must not appear in any log line (JSON
logging of ``ctcv_core`` and the raw ``logging`` records) and no database table may gain a
row. The answer service is a recording fake so the test checks the API layer itself; the
engine's own invariants live in ``tests/invariants/test_ask_invariants.py``.
"""

from __future__ import annotations

import io
import logging
import secrets
import string
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from ctcv_agent.contracts import AskResult
from ctcv_agent.rag.types import KnowledgeBaseNotReady
from ctcv_agent.schemas import SessionContext
from ctcv_api.auth import create_token
from ctcv_api.main import create_app
from ctcv_api.models import Base
from ctcv_api.settings import Settings
from ctcv_core.logging import setup_logging

ASK = "/v1/coach/ask"
# Letters only: no digit run that the PII scrubber could redact (which would hide a leak).
MARKER = "zqxw" + string.ascii_lowercase[::-1][:12] + "kiemtrariengtu"
QUESTION = f"Cháu tên {MARKER}, đăng ký thường trú mất bao nhiêu tiền?"
NOT_SURE = (
    "Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức. "
    "Bác hỏi cán bộ một cửa hoặc tình nguyện viên giúp cháu nhé."
)
PROBE = "privacy-probe-line"


class RecordingService:
    """Answer service that remembers the question, then answers or raises."""

    def __init__(self, outcome: AskResult | Exception) -> None:
        self.outcome = outcome
        self.questions: list[str] = []

    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        self.questions.append(question)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _not_sure() -> AskResult:
    return AskResult(
        answer=NOT_SURE,
        confidence=0.1,
        escalate=True,
        reason="no_source",
        answer_mode="no_source",
    )


def _app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite://",
        jwt_secret=secrets.token_urlsafe(32),  # built at run time: no secret-like literal
        ctcv_env="test",
        log_level="DEBUG",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


def _row_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            table.name: conn.execute(select(func.count()).select_from(table)).scalar_one()
            for table in Base.metadata.sorted_tables
        }


@pytest.fixture
def json_log() -> Iterator[io.StringIO]:
    """Capture the JSON log stream of ``ctcv_core`` at DEBUG level."""
    yield io.StringIO()
    setup_logging("api", level="WARNING")


def _ask(app: FastAPI, json_log: io.StringIO, body: dict) -> tuple[int, str]:
    setup_logging("api", level="DEBUG", stream=json_log)
    logging.getLogger("ctcv_api").warning(PROBE)
    token = create_token("citizen-privacy", "citizen", app.state.settings)
    # No ``with``: the lifespan would dispose the in-memory engine before rows are counted.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(ASK, headers={"Authorization": f"Bearer {token}"}, json=body)
    return response.status_code, response.text


def _assert_not_logged(json_log: io.StringIO, caplog: pytest.LogCaptureFixture) -> None:
    text = json_log.getvalue()
    assert PROBE in text, "log capture is not working"
    assert MARKER not in text
    assert MARKER not in caplog.text
    for record in caplog.records:
        assert MARKER not in str(record.__dict__)


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (_not_sure(), 200),
        (KnowledgeBaseNotReady("index_missing"), 503),
        (RuntimeError(f"engine failed on: {QUESTION}"), 500),
        (ValueError(QUESTION), 500),
    ],
    ids=["answered", "kb-not-ready", "crash-with-question", "value-error-with-question"],
)
def test_question_is_never_logged_nor_echoed(caplog, json_log, outcome, status):
    caplog.set_level(logging.DEBUG)
    app = _app()
    service = RecordingService(outcome)
    app.state.answer_service = service
    code, text = _ask(app, json_log, {"question": QUESTION})
    assert code == status
    assert service.questions == [QUESTION], "the question must actually reach the service"
    assert MARKER not in text
    _assert_not_logged(json_log, caplog)


def test_rejected_question_is_not_echoed_nor_logged(caplog, json_log):
    caplog.set_level(logging.DEBUG)
    app = _app()
    service = RecordingService(_not_sure())
    app.state.answer_service = service
    code, text = _ask(app, json_log, {"question": QUESTION * 20})
    assert code == 422
    assert service.questions == []
    assert MARKER not in text
    _assert_not_logged(json_log, caplog)


@pytest.mark.parametrize(
    "outcome",
    [_not_sure(), KnowledgeBaseNotReady("index_missing"), RuntimeError("boom")],
    ids=["answered", "kb-not-ready", "crash"],
)
def test_asking_adds_no_database_rows(json_log, outcome):
    app = _app()
    app.state.answer_service = RecordingService(outcome)
    before = _row_counts(app.state.engine)
    _ask(app, json_log, {"question": QUESTION})
    assert _row_counts(app.state.engine) == before
    assert set(before) >= {"users", "sessions", "events", "qa_logs", "audit"}
