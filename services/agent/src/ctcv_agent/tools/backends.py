"""Backend interfaces the tools depend on, with deterministic in-memory fakes for E01.

Later epics plug the real sandbox engine (E02), the RAG index (E03), the drills package
(E09) and the database (E02/E10) behind the same protocols. Every sample record below is
fake: the guide chunks point at RFC 2606 ``.example`` hosts and the drill utterances carry
the mandatory "[Mô phỏng]" label (brief D27).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Protocol

from pydantic import Field

from ctcv_agent.schemas import ProcedureId, RedFlag, StrictModel

# ----------------------------------------------------------------------------- data shapes
ElementKind = Literal["button", "input", "text", "banner"]
ActionKind = Literal["tap", "input"]


class ElementView(StrictModel):
    """A visible element of a sandbox screen, as the planner may describe it."""

    id: str
    kind: ElementKind
    label: str
    color: str


class SessionSnapshot(StrictModel):
    """Structured state of a sandbox session (no free text typed by the learner)."""

    session_id: str
    scenario_id: str
    goal: str
    intent_confirmation: str
    screen_id: str
    screen_title: str
    elements: list[ElementView] = Field(default_factory=list)
    steps: int = 0
    mistakes: int = 0
    hints_used: int = 0
    done: bool = False
    coach_line: str = ""


class NextAction(StrictModel):
    """The next valid action of a session (element, colour, label) or ``done``."""

    session_id: str
    done: bool = False
    action: ActionKind | None = None
    element_id: str | None = None
    color: str | None = None
    label: str | None = None
    coach_line: str = ""


class GuideChunk(StrictModel):
    """A chunk of an official guide, with the metadata a citation needs.

    The optional provenance fields (ADR-007 C4) are filled for administrative-procedure
    chunks (``ctcv_agent.rag.index.FileGuideIndex``): the procedure and section the passage
    belongs to, the publishing agency, when CTCV read the page (UTC) and the search score.
    """

    doc_id: str
    url: str
    title: str
    effective_date: date | None = None
    skill: str
    text: str
    procedure_id: ProcedureId | None = None
    section: str | None = Field(default=None, max_length=32, pattern=r"^[a-z][a-z_]*$")
    agency: str | None = Field(default=None, min_length=1, max_length=200)
    fetched_at: datetime | None = None
    score: float | None = None


class DrillOption(StrictModel):
    """One answer option of a drill; ``correct`` is never exposed to the planner."""

    id: str
    text: str
    correct: bool


class DrillSpec(StrictModel):
    """A scam-vaccine drill at behaviour-pattern level (brief §6, D27)."""

    key: str
    channel: Literal["sms", "zalo", "call"]
    impersonates: str
    pretext: str
    utterance: str
    red_flags: list[RedFlag]
    options: list[DrillOption]
    debrief: str
    three_things: list[str]
    label: str = "Đây là mô phỏng"
    severity: int = 1


class DrillGrade(StrictModel):
    """Result of grading one drill answer."""

    drill_id: str
    key: str
    correct: bool
    score: int = Field(ge=0, le=100)
    red_flags: list[RedFlag]
    debrief: str
    three_things: list[str]


# ----------------------------------------------------------------------------- protocols
class SessionStore(Protocol):
    """Read access to sandbox sessions (E02 binds this to ``ctcv_sandbox.engine``)."""

    def get(self, session_id: str) -> SessionSnapshot | None:
        """Return the snapshot of ``session_id`` or None when unknown."""
        ...

    def next_action(self, session_id: str) -> NextAction | None:
        """Return the next valid action of ``session_id`` or None when unknown."""
        ...


class GuideIndex(Protocol):
    """Search over official guides (ADR-007: ``ctcv_agent.rag.index.FileGuideIndex``)."""

    def search(self, query: str, skill: str | None, top_k: int) -> list[GuideChunk]:
        """Return up to ``top_k`` chunks relevant to ``query`` (optionally within ``skill``)."""
        ...

    def get(self, doc_id: str) -> GuideChunk | None:
        """Return the chunk with ``doc_id`` or None."""
        ...


class DrillStore(Protocol):
    """Start and grade drills (E09 binds this to ``ctcv_drills``)."""

    def start(self, key: str) -> tuple[str, DrillSpec] | None:
        """Start a drill for scenario ``key``; return ``(drill_id, spec)`` or None."""
        ...

    def grade(self, drill_id: str, option_id: str) -> DrillGrade | None:
        """Grade ``option_id`` for ``drill_id``; None when the drill or option is unknown."""
        ...


class ProgressSink(Protocol):
    """Append-only learning progress (E10 binds this to the ``sessions``/``drills`` tables)."""

    def record(self, user_id: str, skill: str, level: int) -> int:
        """Append one record and return the total number of records for ``user_id``."""
        ...


class EscalationSink(Protocol):
    """Flags a session for a human volunteer."""

    def flag(self, user_id: str, session_id: str | None, reason: str) -> str:
        """Create a ticket and return its id."""
        ...


@dataclass
class Backends:
    """The five backends a tool may touch; nothing else is reachable from a tool."""

    sessions: SessionStore
    guides: GuideIndex
    drills: DrillStore
    progress: ProgressSink
    escalations: EscalationSink


# ----------------------------------------------------------------------------- sample data
SAMPLE_SCENARIO_ID = "chuyen-khoan-qr"
SAMPLE_GOAL = "Chuyển 200.000đ cho con bằng quét mã QR"
SAMPLE_INTENT_CONFIRMATION = "Bác muốn chuyển tiền cho con hay trả tiền hàng?"

_SCREENS: dict[str, dict] = {
    "home": {
        "title": "Trang chính",
        "elements": [
            ElementView(id="btn_qr", kind="button", label="Quét QR", color="xanh"),
            ElementView(id="btn_promo", kind="banner", label="Ưu đãi hôm nay", color="vàng"),
            ElementView(id="txt_balance", kind="text", label="Số dư", color="trắng"),
        ],
        "next": ("tap", "btn_qr", "scan"),
        "coach_line": "Bác bấm nút xanh có chữ Quét QR nhé.",
    },
    "scan": {
        "title": "Quét mã",
        "elements": [
            ElementView(id="btn_scan", kind="button", label="Quét", color="xanh"),
            ElementView(id="btn_back", kind="button", label="Quay lại", color="xám"),
        ],
        "next": ("tap", "btn_scan", "amount"),
        "coach_line": "Bác đưa máy vào hình vuông của con rồi bấm nút xanh có chữ Quét nhé.",
    },
    "amount": {
        "title": "Nhập số tiền",
        "elements": [
            ElementView(id="amount", kind="input", label="Số tiền", color="trắng"),
            ElementView(id="btn_continue", kind="button", label="Tiếp tục", color="xanh"),
        ],
        "next": ("input", "amount", "confirm"),
        "coach_line": (
            "Bác gõ số tiền vào ô trắng có chữ Số tiền rồi bấm nút xanh có chữ Tiếp tục nhé."
        ),
    },
    "confirm": {
        "title": "Kiểm tra lại",
        "elements": [
            ElementView(id="btn_confirm", kind="button", label="Chuyển tiền", color="đỏ"),
            ElementView(id="btn_cancel", kind="button", label="Hủy", color="xám"),
        ],
        "next": ("tap", "btn_confirm", "done"),
        "coach_line": "Bác xem lại tên người nhận rồi bấm nút đỏ có chữ Chuyển tiền nhé.",
    },
    "done": {
        "title": "Chuyển thành công",
        "elements": [
            ElementView(id="btn_home", kind="button", label="Về trang chính", color="xanh")
        ],
        "next": None,
        "coach_line": "Bác làm tốt lắm, mình xong bài rồi nhé.",
    },
}

# session_id → (screen_id, steps, mistakes, hints_used)
_SAMPLE_SESSIONS: dict[str, tuple[str, int, int, int]] = {
    "sess-demo-1": ("home", 0, 0, 0),
    "sess-demo-2": ("amount", 2, 1, 1),
    "sess-demo-done": ("done", 4, 1, 1),
}

SAMPLE_GUIDES: tuple[GuideChunk, ...] = (
    GuideChunk(
        doc_id="dvc-xac-nhan-cu-tru",
        url="https://dvc.example/huong-dan/xac-nhan-cu-tru",
        title="Hướng dẫn xác nhận thông tin về cư trú trên Cổng Dịch vụ công",
        effective_date=date(2026, 3, 1),
        skill="dich-vu-cong",
        text=(
            "Người dân đăng nhập bằng tài khoản VNeID, chọn mục Xác nhận thông tin về cư trú, "
            "điền tờ khai và gửi. Kết quả trả về trong 1 ngày làm việc "
            "và không thu lệ phí (0 đồng)."
        ),
    ),
    GuideChunk(
        doc_id="vneid-dang-nhap",
        url="https://dvc.example/huong-dan/vneid-dang-nhap",
        title="Đăng nhập ứng dụng VNeID",
        effective_date=date(2026, 1, 15),
        skill="dinh-danh-vneid",
        text=(
            "Mở ứng dụng VNeID, nhập số định danh cá nhân và mật khẩu, "
            "sau đó nhập mã gửi về điện thoại "
            "để đăng nhập. Tài khoản mức 2 phải đăng ký trực tiếp tại cơ quan công an."
        ),
    ),
    GuideChunk(
        doc_id="ngan-hang-chuyen-khoan-qr",
        url="https://nganhang.example/huong-dan/chuyen-khoan-qr",
        title="Chuyển khoản bằng mã QR trên ứng dụng ngân hàng",
        effective_date=date(2025, 11, 20),
        skill="thanh-toan-thue-so",
        text=(
            "Mở ứng dụng ngân hàng, chọn Quét QR, đưa máy vào mã của người nhận, "
            "kiểm tra tên người "
            "nhận rồi nhập số tiền và bấm Chuyển tiền. "
            "Ngân hàng không bao giờ yêu cầu khách hàng đọc "
            "mã OTP qua điện thoại."
        ),
    ),
    GuideChunk(
        doc_id="an-toan-so-nhan-dien-lua-dao",
        url="https://antoan.example/canh-bao/dau-hieu-lua-dao",
        title="Dấu hiệu lừa đảo thường gặp và cách xử lý",
        effective_date=date(2026, 2, 10),
        skill="an-toan-so",
        text=(
            "Dấu hiệu lừa đảo thường gặp: giục chuyển tiền gấp, đòi mã OTP, "
            "tự xưng công an hoặc ngân "
            "hàng, gửi đường link lạ. Người dân không chuyển tiền cho người lạ "
            "và gọi tổng đài chính "
            "thức của ngân hàng để kiểm tra."
        ),
    ),
)

SAMPLE_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        key="gia-danh-cong-an-goi-dien",
        channel="call",
        impersonates="cong-an",
        pretext=(
            "Người gọi tự xưng công an, nói bác liên quan một vụ án và đòi chuyển tiền "
            "để chứng minh trong sạch."
        ),
        utterance=(
            "[Mô phỏng] Tôi là cán bộ điều tra, bác đang liên quan một vụ án; bác chuyển tiền vào "
            "tài khoản tạm giữ để chứng minh trong sạch và không được nói với ai."
        ),
        red_flags=["xung-co-quan", "giuc-chuyen-tien", "giu-bi-mat", "doa-dam", "tai-khoan-la"],
        options=[
            DrillOption(id="a", text="Chuyển tiền ngay để được minh oan", correct=False),
            DrillOption(
                id="b", text="Cúp máy, gọi con cháu hoặc công an phường để kiểm tra", correct=True
            ),
            DrillOption(
                id="c", text="Đọc số tài khoản và mã của mình cho họ kiểm tra", correct=False
            ),
            DrillOption(id="d", text="Xin thêm thời gian rồi đi vay tiền để chuyển", correct=False),
        ],
        debrief=(
            "Công an không bao giờ gọi điện đòi chuyển tiền. "
            "Bác cúp máy và hỏi người thân hoặc công an phường nhé."
        ),
        three_things=[
            "Cúp máy ngay khi bị giục chuyển tiền",
            "Không đọc mã, không chuyển tiền cho người lạ",
            "Gọi người thân hoặc công an phường để kiểm tra",
        ],
        severity=3,
    ),
    DrillSpec(
        key="ngan-hang-khoa-tai-khoan-sms",
        channel="sms",
        impersonates="ngan-hang",
        pretext=(
            "Tin nhắn tự xưng ngân hàng báo tài khoản sắp bị khóa và giục bấm vào đường dẫn lạ."
        ),
        utterance=(
            "[Mô phỏng] Tài khoản của bác sắp bị khóa, "
            "bấm vào đường dẫn trong tin để mở khóa ngay hôm nay."
        ),
        red_flags=["xung-co-quan", "link-la", "doa-dam"],
        options=[
            DrillOption(id="a", text="Bấm vào đường dẫn để mở khóa cho kịp", correct=False),
            DrillOption(id="b", text="Không bấm, gọi tổng đài in trên thẻ để hỏi", correct=True),
            DrillOption(
                id="c", text="Trả lời tin nhắn kèm số tài khoản để họ kiểm tra", correct=False
            ),
        ],
        debrief=(
            "Ngân hàng không gửi đường dẫn để mở khóa qua tin nhắn. "
            "Bác gọi tổng đài in trên thẻ để hỏi nhé."
        ),
        three_things=[
            "Không bấm đường dẫn trong tin nhắn lạ",
            "Không trả lời tin nhắn kèm thông tin tài khoản",
            "Gọi tổng đài in trên thẻ để kiểm tra",
        ],
        severity=2,
    ),
)


# ----------------------------------------------------------------------------- fakes
class InMemorySessionStore:
    """Deterministic sessions on the ``chuyen-khoan-qr`` scenario (brief §5)."""

    def __init__(self, sessions: dict[str, tuple[str, int, int, int]] | None = None) -> None:
        """Seed with ``_SAMPLE_SESSIONS`` unless given explicitly."""
        self._sessions = dict(sessions if sessions is not None else _SAMPLE_SESSIONS)

    def get(self, session_id: str) -> SessionSnapshot | None:
        """Return the snapshot for ``session_id`` or None."""
        row = self._sessions.get(session_id)
        if row is None:
            return None
        screen_id, steps, mistakes, hints = row
        screen = _SCREENS[screen_id]
        return SessionSnapshot(
            session_id=session_id,
            scenario_id=SAMPLE_SCENARIO_ID,
            goal=SAMPLE_GOAL,
            intent_confirmation=SAMPLE_INTENT_CONFIRMATION,
            screen_id=screen_id,
            screen_title=screen["title"],
            elements=list(screen["elements"]),
            steps=steps,
            mistakes=mistakes,
            hints_used=hints,
            done=screen["next"] is None,
            coach_line=screen["coach_line"],
        )

    def next_action(self, session_id: str) -> NextAction | None:
        """Return the next valid action for ``session_id`` or None."""
        row = self._sessions.get(session_id)
        if row is None:
            return None
        screen = _SCREENS[row[0]]
        if screen["next"] is None:
            return NextAction(session_id=session_id, done=True, coach_line=screen["coach_line"])
        kind, element_id, _ = screen["next"]
        element = next(e for e in screen["elements"] if e.id == element_id)
        return NextAction(
            session_id=session_id,
            action=kind,
            element_id=element.id,
            color=element.color,
            label=element.label,
            coach_line=screen["coach_line"],
        )


class InMemoryGuideIndex:
    """Token-overlap search over :data:`SAMPLE_GUIDES`."""

    def __init__(self, chunks: tuple[GuideChunk, ...] = SAMPLE_GUIDES) -> None:
        """Index ``chunks`` by ``doc_id``."""
        self._chunks = {c.doc_id: c for c in chunks}

    def search(self, query: str, skill: str | None, top_k: int) -> list[GuideChunk]:
        """Rank chunks by overlap with ``query``; drop zero-overlap chunks."""
        from ctcv_agent.verify import tokenize

        wanted = tokenize(query)
        scored: list[tuple[int, str, GuideChunk]] = []
        for chunk in self._chunks.values():
            if skill and chunk.skill != skill:
                continue
            hits = len(wanted & tokenize(f"{chunk.title} {chunk.text}"))
            if hits:
                scored.append((-hits, chunk.doc_id, chunk))
        scored.sort()
        return [c for _, _, c in scored[:top_k]]

    def get(self, doc_id: str) -> GuideChunk | None:
        """Return the chunk with ``doc_id`` or None."""
        return self._chunks.get(doc_id)


class InMemoryDrillStore:
    """Drills from :data:`SAMPLE_DRILLS`; started drills get sequential ids ``drill-0001``."""

    def __init__(self, specs: tuple[DrillSpec, ...] = SAMPLE_DRILLS) -> None:
        """Index ``specs`` by key; no drill started yet."""
        self._specs = {s.key: s for s in specs}
        self._active: dict[str, DrillSpec] = {}

    def start(self, key: str) -> tuple[str, DrillSpec] | None:
        """Start a drill for ``key``; unknown keys return None."""
        spec = self._specs.get(key)
        if spec is None:
            return None
        drill_id = f"drill-{len(self._active) + 1:04d}"
        self._active[drill_id] = spec
        return drill_id, spec

    def grade(self, drill_id: str, option_id: str) -> DrillGrade | None:
        """Grade ``option_id``; None when the drill or option is unknown."""
        spec = self._active.get(drill_id)
        if spec is None:
            return None
        option = next((o for o in spec.options if o.id == option_id), None)
        if option is None:
            return None
        return DrillGrade(
            drill_id=drill_id,
            key=spec.key,
            correct=option.correct,
            score=100 if option.correct else 0,
            red_flags=list(spec.red_flags),
            debrief=spec.debrief,
            three_things=list(spec.three_things),
        )


@dataclass
class InMemoryProgressSink:
    """Progress records kept in a list (``(user_id, skill, level)``)."""

    records: list[tuple[str, str, int]] = field(default_factory=list)

    def record(self, user_id: str, skill: str, level: int) -> int:
        """Append and return the user's record count."""
        self.records.append((user_id, skill, level))
        return sum(1 for r in self.records if r[0] == user_id)


@dataclass
class InMemoryEscalationSink:
    """Escalation tickets kept in a list (``(ticket_id, user_id, session_id, reason)``)."""

    tickets: list[tuple[str, str, str | None, str]] = field(default_factory=list)

    def flag(self, user_id: str, session_id: str | None, reason: str) -> str:
        """Create ``esc-NNNN`` and return it."""
        ticket_id = f"esc-{len(self.tickets) + 1:04d}"
        self.tickets.append((ticket_id, user_id, session_id, reason))
        return ticket_id


def in_memory_backends() -> Backends:
    """Fresh, independent in-memory backends seeded with the sample data."""
    return Backends(
        sessions=InMemorySessionStore(),
        guides=InMemoryGuideIndex(),
        drills=InMemoryDrillStore(),
        progress=InMemoryProgressSink(),
        escalations=InMemoryEscalationSink(),
    )


_default: Backends | None = None


def default_backends() -> Backends:
    """Process-wide backends used when the router is called without explicit ones."""
    global _default
    if _default is None:
        _default = in_memory_backends()
    return _default


def set_default_backends(backends: Backends | None) -> None:
    """Replace (or reset with None) the process-wide backends — the API wires real ones here."""
    global _default
    _default = backends


def sample_turn_state(session_id: str = "sess-demo-1") -> dict:
    """Structured state the API passes to ``coach.run_turn`` for a sample session."""
    store = InMemorySessionStore()
    snapshot = store.get(session_id)
    nxt = store.next_action(session_id)
    if snapshot is None or nxt is None:
        raise KeyError(session_id)
    return {**snapshot.model_dump(mode="json"), "next_action": nxt.model_dump(mode="json")}
