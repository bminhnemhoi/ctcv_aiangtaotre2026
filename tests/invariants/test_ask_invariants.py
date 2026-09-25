"""Invariant (c) for the TTHC answer engine (ADR-007): no invented number, no uncited fact.

* In the default mode a number the composer invents never reaches the citizen: every number
  of the answer occurs in the chunks it cites.
* Without a trustworthy source the engine says "chưa chắc", escalates and cites nothing.
* "Free" is never said unless every channel of the record says so (P1: 17/107 records have
  no readable fee; "Đăng ký tạm trú" shows "Phí: 1").
* Answering writes no file and never logs the question verbatim (invariant (b)).
"""

from __future__ import annotations

import builtins
import io
import json
import logging
import os
from pathlib import Path

import pytest

from ctcv_agent.answer_templates import NO_SOURCE_LINE, claims_free
from ctcv_agent.ask import build_engine
from ctcv_agent.compose import FakeComposer
from ctcv_agent.guardrails import requires_citation
from ctcv_agent.numeric import canonical_numbers, numbers_supported
from ctcv_agent.rag.fake import FakeKnowledgeBase
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import ProcedureRecord
from ctcv_agent.schemas import SessionContext
from ctcv_core.config import find_repo_root

RECORDS_DIR = find_repo_root() / "services" / "agent" / "tests" / "fixtures" / "tthc" / "records"
DENSE = {"1.004222": 0.62, "2.000200": 0.66, "1.004194": 0.6}
CTX = SessionContext(user_id="user-demo", session_id="sess-demo-1")
QUESTIONS = [
    "Đăng ký thường trú mất bao nhiêu tiền?",
    "Đăng ký thường trú bao lâu thì xong?",
    "Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?",
    "Đăng ký tạm trú nộp ở đâu?",
    "Đăng ký thường trú theo luật nào?",
    "Làm căn cước làm thế nào?",
]
INVENTED = [
    "Bác nộp hồ sơ trực tiếp thì mất 15.000 đồng mỗi lần đăng ký.",
    "Bác chờ 3 ngày làm việc là có kết quả đăng ký thường trú.",
    "Theo Nghị định 99/2030/NĐ-CP, bác nộp 20.000 đồng và 5 bản sao.",
    "Bác mang hai bản sao giấy tờ chứng minh chỗ ở hợp pháp nhé.",
    "Làm căn cước cho người từ đủ 15 tuổi mất 7 ngày làm việc.",
]
OUT_OF_SCOPE = [
    "Thủ tục đăng ký kết hôn cần những gì?",
    "Xin giấy phép xây dựng nhà ở nông thôn thế nào?",
    "zzzz qqqq",
]


@pytest.fixture(scope="module")
def settings() -> RagSettings:
    return load_rag_settings()


@pytest.fixture(scope="module")
def records() -> list[ProcedureRecord]:
    return [ProcedureRecord.load(p) for p in sorted(RECORDS_DIR.glob("*.json"))]


def _engine(records, settings, answer: str, dense=DENSE):
    kb = FakeKnowledgeBase(records, dense, settings=settings)
    reply = json.dumps({"answer": answer, "doc_ids": []}, ensure_ascii=False)
    return kb, build_engine(settings, kb=kb, composer=FakeComposer([reply]))


@pytest.mark.parametrize("invented", INVENTED)
@pytest.mark.parametrize("question", QUESTIONS)
def test_invented_numbers_never_reach_the_citizen(records, settings, question, invented) -> None:
    kb, engine = _engine(records, settings, invented)
    assert engine.mode == "llm_verified"  # the default mode from config/rag.yaml
    result = engine.ask(question, CTX)
    sources = [kb.get_chunk(c.doc_id).text for c in result.citations]
    check = numbers_supported(result.answer, sources)
    assert check.ok, (result.answer, check.unsupported)
    if result.answer_mode == "llm_verified":
        assert canonical_numbers(invented) <= set().union(*map(canonical_numbers, sources))
    assert result.answer_mode != "llm_unverified"


@pytest.mark.parametrize("question", OUT_OF_SCOPE)
def test_no_source_means_escalation_and_no_citation(records, settings, question) -> None:
    _, engine = _engine(records, settings, "Bác nộp 20.000 đồng mỗi lần đăng ký nhé.")
    result = engine.ask(question, CTX)
    assert result.answer == NO_SOURCE_LINE and result.answer_mode == "no_source"
    assert result.escalate is True and result.citations == [] and result.procedure is None


def test_weak_retrieval_means_escalation(records, settings) -> None:
    low = {pid: 0.2 for pid in DENSE}
    _, engine = _engine(records, settings, "Bác nộp 20.000 đồng.", dense=low)
    for question in QUESTIONS:
        result = engine.ask(question, CTX)
        assert result.escalate is True and result.citations == [], question
        assert requires_citation(result.answer, result.citations) is False


FREE_CLAIMS = [
    "Đăng ký tạm trú miễn phí bác nhé.",
    "Đăng ký thường trú không mất tiền đâu bác.",
    "Lệ phí đăng ký tạm trú là 0 đồng.",
]
FEE_QUESTIONS = [
    "Đăng ký tạm trú mất bao nhiêu tiền?",
    "Đăng ký tạm trú có mất tiền không?",
    "Đăng ký thường trú mất bao nhiêu tiền?",
]


@pytest.mark.parametrize("claim", FREE_CLAIMS)
@pytest.mark.parametrize("question", FEE_QUESTIONS)
def test_free_is_never_claimed_without_a_source_saying_so(records, settings, question, claim):
    _, engine = _engine(records, settings, claim)
    result = engine.ask(question, CTX)
    assert not claims_free(result.answer), result.answer
    assert requires_citation(result.answer, result.citations) is False


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in root.rglob("*")
    }


def test_answer_engine_writes_no_file(records, settings, tmp_path, monkeypatch) -> None:
    _, engine = _engine(records, settings, "Bác nộp 20.000 đồng mỗi lần đăng ký nhé.")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    before = _snapshot(tmp_path)
    writes: list[str] = []
    real_open, real_os_open = builtins.open, os.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND):
            writes.append(str(path))
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    for question in [*QUESTIONS, *OUT_OF_SCOPE, "Có người xin mã OTP, tôi có đọc không?"]:
        engine.ask(question, CTX)
    assert writes == []
    assert _snapshot(tmp_path) == before


def test_question_is_never_logged(records, settings, caplog) -> None:
    marker = "Đăng ký thường trú mất bao nhiêu tiền hỏi-riêng-ZQX"
    _, engine = _engine(records, settings, "KHONG_CHAC")
    with caplog.at_level(logging.DEBUG):
        engine.ask(marker, CTX)
    assert "ZQX" not in caplog.text
