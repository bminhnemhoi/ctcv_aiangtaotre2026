"""One test group per tool (brief §7: "test riêng")."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctcv_agent.schemas import SessionContext
from ctcv_agent.tools import (
    escalate_to_volunteer,
    get_session_state,
    grade_drill,
    log_progress,
    next_step,
    search_guides,
    start_drill,
    verify_citation,
)
from ctcv_agent.tools.backends import (
    Backends,
    InMemoryDrillStore,
    InMemoryGuideIndex,
    InMemorySessionStore,
    in_memory_backends,
    sample_turn_state,
)
from ctcv_core.errors import Forbidden, NotFound


class TestGetSessionState:
    def test_reads_sample_session(self, ctx: SessionContext, backends: Backends) -> None:
        out = get_session_state.run(
            get_session_state.Input(session_id="sess-demo-1"), ctx, backends
        )
        assert out.screen_id == "home" and out.scenario_id == "chuyen-khoan-qr"
        assert [e.id for e in out.elements] == ["btn_qr", "btn_promo", "txt_balance"]
        assert out.done is False and out.steps == 0

    def test_unknown_session(self, backends: Backends) -> None:
        ctx = SessionContext(user_id="u")
        with pytest.raises(NotFound) as exc:
            get_session_state.run(get_session_state.Input(session_id="nope"), ctx, backends)
        assert exc.value.code == "SESSION_NOT_FOUND"

    def test_other_session_forbidden(self, ctx: SessionContext, backends: Backends) -> None:
        with pytest.raises(Forbidden):
            get_session_state.run(get_session_state.Input(session_id="sess-demo-2"), ctx, backends)

    def test_done_session(self, backends: Backends) -> None:
        ctx = SessionContext(user_id="u", session_id="sess-demo-done")
        out = get_session_state.run(
            get_session_state.Input(session_id="sess-demo-done"), ctx, backends
        )
        assert out.done is True


class TestNextStep:
    def test_home_points_to_qr_button(self, ctx: SessionContext, backends: Backends) -> None:
        out = next_step.run(next_step.Input(session_id="sess-demo-1"), ctx, backends)
        assert (out.action, out.element_id, out.color, out.label) == (
            "tap",
            "btn_qr",
            "xanh",
            "Quét QR",
        )
        assert out.coach_line.endswith("nhé.")

    def test_amount_screen_is_input(self, backends: Backends) -> None:
        ctx = SessionContext(user_id="u", session_id="sess-demo-2")
        out = next_step.run(next_step.Input(session_id="sess-demo-2"), ctx, backends)
        assert out.action == "input" and out.element_id == "amount"

    def test_done_session(self, backends: Backends) -> None:
        ctx = SessionContext(user_id="u", session_id="sess-demo-done")
        out = next_step.run(next_step.Input(session_id="sess-demo-done"), ctx, backends)
        assert out.done is True and out.element_id is None

    def test_unknown_session(self, backends: Backends) -> None:
        with pytest.raises(NotFound):
            next_step.run(next_step.Input(session_id="nope"), SessionContext(user_id="u"), backends)

    def test_forbidden_session(self, ctx: SessionContext, backends: Backends) -> None:
        with pytest.raises(Forbidden):
            next_step.run(next_step.Input(session_id="sess-demo-2"), ctx, backends)

    def test_sample_turn_state_includes_next_action(self) -> None:
        state = sample_turn_state("sess-demo-1")
        assert state["next_action"]["element_id"] == "btn_qr"
        with pytest.raises(KeyError):
            sample_turn_state("nope")


class TestSearchGuides:
    def test_finds_cu_tru_guide(self, ctx: SessionContext, backends: Backends) -> None:
        out = search_guides.run(search_guides.Input(query="xác nhận cư trú lệ phí"), ctx, backends)
        assert out.results and out.results[0].doc_id == "dvc-xac-nhan-cu-tru"
        assert out.results[0].url.startswith("https://")

    def test_skill_filter(self, ctx: SessionContext, backends: Backends) -> None:
        out = search_guides.run(
            search_guides.Input(query="mã OTP ngân hàng", skill="an-toan-so"), ctx, backends
        )
        assert {r.skill for r in out.results} == {"an-toan-so"}

    def test_invalid_skill_rejected(self) -> None:
        with pytest.raises(ValidationError):
            search_guides.Input(query="abc", skill="hacking")

    def test_no_match(self, ctx: SessionContext, backends: Backends) -> None:
        out = search_guides.run(search_guides.Input(query="zzzz qqqq"), ctx, backends)
        assert out.results == []

    def test_top_k_bounds(self) -> None:
        with pytest.raises(ValidationError):
            search_guides.Input(query="abc", top_k=11)
        assert search_guides.Input(query="abc", top_k=1).top_k == 1


class TestVerifyCitation:
    def test_supported_claim(self, ctx: SessionContext, backends: Backends) -> None:
        inp = verify_citation.Input(
            claim=(
                "Xác nhận thông tin cư trú không thu lệ phí, kết quả trả về trong 1 ngày làm việc"
            ),
            doc_id="dvc-xac-nhan-cu-tru",
        )
        out = verify_citation.run(inp, ctx, backends)
        assert out.supported is True and out.score >= 0.6
        assert out.title.startswith("Hướng dẫn") and out.quote

    def test_unsupported_claim(self, ctx: SessionContext, backends: Backends) -> None:
        inp = verify_citation.Input(
            claim="Lệ phí cấp hộ chiếu là hai trăm nghìn", doc_id="dvc-xac-nhan-cu-tru"
        )
        out = verify_citation.run(inp, ctx, backends)
        assert out.supported is False

    def test_unknown_doc(self, ctx: SessionContext, backends: Backends) -> None:
        with pytest.raises(NotFound) as exc:
            verify_citation.run(
                verify_citation.Input(claim="bất kỳ dữ kiện", doc_id="nope"), ctx, backends
            )
        assert exc.value.code == "DOC_NOT_FOUND"


class TestStartDrill:
    def test_starts_without_leaking_answers(self, ctx: SessionContext, backends: Backends) -> None:
        out = start_drill.run(start_drill.Input(key="gia-danh-cong-an-goi-dien"), ctx, backends)
        assert out.drill_id == "drill-0001" and out.label == "Đây là mô phỏng"
        assert "[Mô phỏng]" in out.utterance
        assert "correct" not in out.model_dump()["options"][0]
        assert out.red_flags_count == 5

    def test_ids_are_sequential(self, ctx: SessionContext, backends: Backends) -> None:
        first = start_drill.run(start_drill.Input(key="gia-danh-cong-an-goi-dien"), ctx, backends)
        second = start_drill.run(
            start_drill.Input(key="ngan-hang-khoa-tai-khoan-sms"), ctx, backends
        )
        assert (first.drill_id, second.drill_id) == ("drill-0001", "drill-0002")

    def test_unknown_key(self, ctx: SessionContext, backends: Backends) -> None:
        with pytest.raises(NotFound):
            start_drill.run(start_drill.Input(key="khong-co"), ctx, backends)


class TestGradeDrill:
    def test_correct_and_wrong(self, ctx: SessionContext, backends: Backends) -> None:
        started = start_drill.run(start_drill.Input(key="gia-danh-cong-an-goi-dien"), ctx, backends)
        good = grade_drill.run(
            grade_drill.Input(drill_id=started.drill_id, option_id="b"), ctx, backends
        )
        assert good.correct and good.score == 100 and len(good.three_things) == 3
        assert "xung-co-quan" in good.red_flags
        bad = grade_drill.run(
            grade_drill.Input(drill_id=started.drill_id, option_id="a"), ctx, backends
        )
        assert not bad.correct and bad.score == 0

    def test_unknown_drill_or_option(self, ctx: SessionContext, backends: Backends) -> None:
        with pytest.raises(NotFound):
            grade_drill.run(grade_drill.Input(drill_id="drill-9999", option_id="a"), ctx, backends)
        started = start_drill.run(start_drill.Input(key="gia-danh-cong-an-goi-dien"), ctx, backends)
        with pytest.raises(NotFound):
            grade_drill.run(
                grade_drill.Input(drill_id=started.drill_id, option_id="z"), ctx, backends
            )


class TestLogProgress:
    def test_records_context_user(self, ctx: SessionContext, backends: Backends) -> None:
        out = log_progress.run(log_progress.Input(skill="dich-vu-cong", level=1), ctx, backends)
        assert out.total_records == 1 and out.recorded
        other = SessionContext(user_id="user-b")
        log_progress.run(log_progress.Input(skill="dich-vu-cong", level=2), other, backends)
        again = log_progress.run(log_progress.Input(skill="an-toan-so", level=3), ctx, backends)
        assert again.total_records == 2
        assert backends.progress.records[1] == ("user-b", "dich-vu-cong", 2)

    def test_input_has_no_user_id_and_level_bounds(self) -> None:
        assert "user_id" not in log_progress.Input.model_fields
        with pytest.raises(ValidationError):
            log_progress.Input(skill="dich-vu-cong", level=4)
        with pytest.raises(ValidationError):
            log_progress.Input(skill="hacking", level=1)


class TestEscalateToVolunteer:
    def test_creates_ticket_and_redacts_reason(
        self, ctx: SessionContext, backends: Backends
    ) -> None:
        out = escalate_to_volunteer.run(
            escalate_to_volunteer.Input(reason="người học đọc mã OTP 123456 và số 0912345678"),
            ctx,
            backends,
        )
        assert out.escalated and out.ticket_id == "esc-0001"
        ticket = backends.escalations.tickets[0]
        assert ticket[1:3] == ("user-demo", "sess-demo-1")
        assert "123456" not in ticket[3] and "0912345678" not in ticket[3]

    def test_reason_length(self) -> None:
        with pytest.raises(ValidationError):
            escalate_to_volunteer.Input(reason="x" * 201)
        with pytest.raises(ValidationError):
            escalate_to_volunteer.Input(reason="")


class TestBackends:
    def test_fresh_backends_are_independent(self) -> None:
        a, b = in_memory_backends(), in_memory_backends()
        a.progress.record("u", "an-toan-so", 1)
        assert b.progress.records == []

    def test_store_helpers(self) -> None:
        store = InMemorySessionStore({"s1": ("confirm", 3, 0, 0)})
        assert store.get("s1").screen_id == "confirm"
        assert store.next_action("s1").color == "đỏ"
        assert store.get("missing") is None and store.next_action("missing") is None
        assert InMemoryGuideIndex().get("missing") is None
        drills = InMemoryDrillStore()
        assert drills.start("missing") is None and drills.grade("missing", "a") is None
