"""``ctcv_api.knowledge``: lazy, locked, shared wiring of the answer and intake services.

The first half drives the singleton logic with a stubbed builder. The second half runs the
real ``AnswerEngine`` and ``IntakeChecker`` (ADR-007 C4, P3) over the in-memory
``FakeKnowledgeBase`` and a scripted ``FakeComposer`` end to end through HTTP — no model
server, no index on disk. Engine modules are imported inside fixtures so the singleton tests
stay independent of them.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from ctcv_api import knowledge

ASK = "/v1/coach/ask"
INTAKE = "/v1/coach/intake-check"
# Fixed dense scores per procedure, as in the agent tests: every fixture passes the gate.
DENSE = {"1.004222": 0.62, "2.000200": 0.66, "1.004194": 0.6}
FEE_Q = "Đăng ký thường trú mất bao nhiêu tiền?"
OUT_OF_KB_Q = "Thủ tục đăng ký kết hôn cần những gì?"
OTP_Q = "Có người xưng công an gọi xin mã OTP, tôi có đọc không?"
FEE_CHUNK = "tthc-1.004222-phi_le_phi-0"
GOOD_FEE_SENTENCE = (
    "Bác nộp hồ sơ trực tiếp thì mất 20.000 đồng mỗi lần đăng ký, "
    "còn nộp trực tuyến thì mất 10.000 đồng mỗi lần."
)
INVENTED_FEE_SENTENCE = "Bác nộp hồ sơ trực tiếp thì mất 15.000 đồng mỗi lần đăng ký."


class _Answer:
    def __init__(self, name: str) -> None:
        self.name = name

    def ask(self, question, ctx):  # pragma: no cover - identity only
        raise AssertionError("not called")


class _Intake:
    def check(self, req):  # pragma: no cover - identity only
        raise AssertionError("not called")


# ---------------------------------------------------------------- lazy singleton
def test_both_services_are_built_once_on_first_use(monkeypatch):
    built = knowledge.KnowledgeServices(answer=_Answer("a"), intake=_Intake())
    calls: list[int] = []

    def _build():
        calls.append(1)
        return built

    monkeypatch.setattr(knowledge, "build_services", _build)
    state = SimpleNamespace(answer_service=None, intake_service=None)
    assert knowledge._service(state, knowledge.ANSWER_ATTR) is built.answer
    assert knowledge._service(state, knowledge.INTAKE_ATTR) is built.intake
    assert knowledge._service(state, knowledge.ANSWER_ATTR) is built.answer
    assert calls == [1]


def test_missing_state_attributes_count_as_unset(monkeypatch):
    built = knowledge.KnowledgeServices(answer=_Answer("a"), intake=_Intake())
    monkeypatch.setattr(knowledge, "build_services", lambda: built)
    state = SimpleNamespace()
    assert knowledge._service(state, knowledge.INTAKE_ATTR) is built.intake
    assert state.answer_service is built.answer


def test_preset_service_is_kept_when_the_other_one_is_built(monkeypatch):
    preset = _Answer("preset")
    built = knowledge.KnowledgeServices(answer=_Answer("built"), intake=_Intake())
    monkeypatch.setattr(knowledge, "build_services", lambda: built)
    state = SimpleNamespace(answer_service=preset, intake_service=None)
    assert knowledge._service(state, knowledge.INTAKE_ATTR) is built.intake
    assert state.answer_service is preset


def test_preset_intake_is_kept_when_answer_is_built(monkeypatch):
    preset = _Intake()
    built = knowledge.KnowledgeServices(answer=_Answer("built"), intake=_Intake())
    monkeypatch.setattr(knowledge, "build_services", lambda: built)
    state = SimpleNamespace(answer_service=None, intake_service=preset)
    assert knowledge._service(state, knowledge.ANSWER_ATTR) is built.answer
    assert state.intake_service is preset


def test_concurrent_first_requests_build_only_once(monkeypatch):
    built = knowledge.KnowledgeServices(answer=_Answer("a"), intake=_Intake())
    calls: list[int] = []

    def _slow_build():
        calls.append(1)
        time.sleep(0.05)
        return built

    monkeypatch.setattr(knowledge, "build_services", _slow_build)
    state = SimpleNamespace(answer_service=None, intake_service=None)
    barrier = threading.Barrier(8)
    seen: list[object] = []

    def _worker(attr: str) -> None:
        barrier.wait()
        seen.append(knowledge._service(state, attr))

    attrs = [knowledge.ANSWER_ATTR, knowledge.INTAKE_ATTR] * 4
    threads = [threading.Thread(target=_worker, args=(attr,)) for attr in attrs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert calls == [1]
    assert len(seen) == 8 and {id(s) for s in seen} == {id(built.answer), id(built.intake)}


def test_dependencies_read_the_application_state(monkeypatch):
    built = knowledge.KnowledgeServices(answer=_Answer("a"), intake=_Intake())
    monkeypatch.setattr(knowledge, "build_services", lambda: built)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert knowledge.get_answer_service(request) is built.answer
    assert knowledge.get_intake_service(request) is built.intake


# ---------------------------------------------------------------- real engine, end to end
def _reply(answer: str, doc_ids: tuple[str, ...] = (FEE_CHUNK,)) -> str:
    """Raw JSON the composer model would return."""
    return json.dumps({"answer": answer, "doc_ids": list(doc_ids)}, ensure_ascii=False)


NOT_SURE = _reply("KHONG_CHAC", ())


@pytest.fixture
def rag_settings():
    from ctcv_agent.rag.settings import load_rag_settings

    return load_rag_settings()


@pytest.fixture
def wire(app, monkeypatch, tthc_records, rag_settings) -> Callable[..., Any]:
    """Let the app build its services for real on a ``FakeKnowledgeBase`` + scripted composer.

    ``dense`` fixes the dense score per procedure (drives the answer gate); ``None`` keeps the
    fake's token-overlap score, which ranks procedures by name for the intake search.
    """
    from ctcv_agent.compose import FakeComposer
    from ctcv_agent.rag.fake import FakeKnowledgeBase

    real_build = knowledge.build_services
    builds: list[Any] = []

    def _wire(*replies: str, dense: dict[str, float] | None = DENSE) -> Any:
        kb = FakeKnowledgeBase(list(tthc_records.values()), dense, settings=rag_settings)
        composer = FakeComposer(list(replies) or [NOT_SURE])  # needs ≥ 1 scripted reply

        def _build() -> knowledge.KnowledgeServices:
            services = real_build(rag_settings, kb=kb, composer=composer)
            builds.append(services)
            return services

        app.state.answer_service = None
        app.state.intake_service = None
        monkeypatch.setattr(knowledge, "build_services", _build)
        return SimpleNamespace(composer=composer, builds=builds)

    return _wire


def test_fee_question_gets_a_verified_cited_answer(client, auth_headers, wire):
    from ctcv_agent.answer_templates import CLOSING_DEFAULT

    wired = wire(_reply(GOOD_FEE_SENTENCE))
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_Q})
    assert response.status_code == 200
    body = response.json()
    assert "diagnostics" not in body
    assert body["answer"] == f"{GOOD_FEE_SENTENCE} {CLOSING_DEFAULT}"
    assert (body["answer_mode"], body["reason"], body["refused"]) == ("llm_verified", "ok", False)
    assert [c["doc_id"] for c in body["citations"]] == [FEE_CHUNK]
    citation = body["citations"][0]
    assert citation["procedure_id"] == "1.004222" and citation["section"] == "phi_le_phi"
    assert "20.000" in citation["quote"] and citation["fetched_at"]
    assert body["procedure"]["procedure_id"] == "1.004222"
    assert [f["amounts_vnd"] for f in body["procedure"]["fees"]] == [[20000], [10000]]
    assert len(wired.composer.calls) == 1


def test_invented_fee_never_reaches_the_citizen(client, auth_headers, wire):
    wire(_reply(INVENTED_FEE_SENTENCE))
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_Q})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_mode"] == "template"
    assert "15.000" not in body["answer"] and "20.000" in body["answer"]
    assert body["citations"]


def test_question_outside_the_knowledge_base_escalates(client, auth_headers, wire):
    wired = wire(_reply(GOOD_FEE_SENTENCE))
    question = {"question": OUT_OF_KB_Q}
    body = client.post(ASK, headers=auth_headers("citizen"), json=question).json()
    assert body["escalate"] is True and body["citations"] == []
    assert body["reason"] == "no_source" and body["answer_mode"] == "no_source"
    assert body["procedure"] is None
    assert wired.composer.calls == []


def test_otp_question_gets_the_safety_line(client, auth_headers, wire):
    from ctcv_agent.answer_templates import SENSITIVE_LINE

    wired = wire(_reply(GOOD_FEE_SENTENCE))
    body = client.post(ASK, headers=auth_headers("citizen"), json={"question": OTP_Q}).json()
    assert body["answer"] == SENSITIVE_LINE
    assert (body["refused"], body["reason"], body["answer_mode"]) == (True, "sensitive", "safety")
    assert wired.composer.calls == []


def test_intake_check_lists_received_and_missing_documents(client, auth_headers, wire):
    wire()
    body = {"procedure_id": "2.000200", "received": ["d01"]}
    response = client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert response.status_code == 200
    out = response.json()
    assert {i["doc_key"]: i["status"] for i in out["items"]} == {"d01": "da_nhan", "d04": "thieu"}
    assert out["missing_count"] == 1 and out["needs_case"] is True
    assert out["citations"]
    assert all(c["section"] == "thanh_phan_ho_so" for c in out["citations"])


def test_intake_check_finds_the_procedure_by_name(client, auth_headers, wire):
    wire(dense=None)
    body = {"query": "đăng ký tạm trú", "received": ["d01", "d02"]}
    out = client.post(INTAKE, headers=auth_headers("volunteer"), json=body).json()
    assert out["procedure"]["procedure_id"] == "1.004194"
    assert out["alternatives"] and len(out["alternatives"]) <= 3


def test_intake_check_unknown_case_is_422(client, auth_headers, wire):
    wire()
    body = {"procedure_id": "2.000200", "case_label": "Trường hợp không có"}
    response = client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_intake_check_unknown_procedure_is_404(client, auth_headers, wire):
    wire()
    response = client.post(INTAKE, headers=auth_headers("officer"), json={"procedure_id": "9.999"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROCEDURE_NOT_FOUND"


def test_ask_and_intake_share_one_build_and_the_tools_read_the_same_kb(client, auth_headers, wire):
    from ctcv_agent.rag.index import FileGuideIndex
    from ctcv_agent.tools.backends import default_backends

    wired = wire(_reply(GOOD_FEE_SENTENCE))
    client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_Q})
    client.post(INTAKE, headers=auth_headers("officer"), json={"procedure_id": "2.000200"})
    assert len(wired.builds) == 1
    guides = default_backends().guides
    assert isinstance(guides, FileGuideIndex)
    assert guides.get(FEE_CHUNK) is not None


def test_missing_index_on_disk_is_503_and_not_cached(
    client, app, auth_headers, monkeypatch, tmp_path, rag_settings
):
    empty = dataclasses.replace(
        rag_settings,
        kb=dataclasses.replace(
            rag_settings.kb, index_dir=tmp_path / "index", records_dir=tmp_path / "records"
        ),
    )
    real_build = knowledge.build_services
    monkeypatch.setattr(knowledge, "build_services", lambda: real_build(empty))
    app.state.answer_service = None
    app.state.intake_service = None
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_Q})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KB_NOT_READY"
    assert app.state.answer_service is None and app.state.intake_service is None


def test_real_engine_path_does_not_log_the_question(client, auth_headers, wire, caplog):
    caplog.set_level(logging.DEBUG)
    wired = wire(_reply(GOOD_FEE_SENTENCE))
    marker = "zqxwvkiemtrariengtu"
    question = f"Cháu tên {marker}, đăng ký thường trú mất bao nhiêu tiền?"
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": question})
    assert response.status_code == 200
    assert len(wired.builds) == 1, "the question must reach the real engine"
    assert marker not in caplog.text
    for record in caplog.records:
        assert marker not in str(record.__dict__)
