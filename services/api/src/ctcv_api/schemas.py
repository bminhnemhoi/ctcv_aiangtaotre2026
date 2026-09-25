"""Request/response models for every endpoint of brief §3 and ADR-007 C6 (Vietnamese fields).

Request models forbid unknown keys so contract drift is caught at the edge; response
models are the wire format the web app relies on.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ctcv_agent.contracts import MAX_CASE_LABEL, ChecklistStatus, Reason
from ctcv_agent.rag.types import Channel
from ctcv_agent.schemas import PROCEDURE_ID_PATTERN
from ctcv_api.enums import AccentPref, Role

SLUG_PATTERN = r"^[a-z0-9-]+$"
DISPLAY_NAME_MAX = 32
QUESTION_MAX = 500
TTS_TEXT_MAX = 500
THREE_THINGS = 3
DOC_KEY_PATTERN = r"^d\d{2}$"
RECEIVED_MAX = 60
QUERY_MIN, QUERY_MAX = 2, 200
SESSION_ID_MAX = 64  # red-team F-10: a 200 000-character session id was accepted
CASE_LABEL_MAX = MAX_CASE_LABEL  # same bound as the agent contract (red-team F-09)
PROCEDURE_ID_MAX = 40


class RequestModel(BaseModel):
    """Base for request bodies: unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    """Base for response bodies."""

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- errors
class ErrorDetail(ResponseModel):
    """Body of ``error`` in the unified error format."""

    code: str = Field(description="Mã lỗi ổn định (UPPER_SNAKE), ví dụ SCENARIO_NOT_FOUND")
    message: str = Field(description="Câu tiếng Việt an toàn để hiển thị cho người dân")
    details: dict[str, Any] | None = Field(default=None, description="Ngữ cảnh máy đọc, không PII")


class ErrorResponse(ResponseModel):
    """Unified error envelope ``{"error": {code, message[, details]}}``."""

    error: ErrorDetail = Field(description="Chi tiết lỗi")


# ---------------------------------------------------------------- auth
class JoinRequest(RequestModel):
    """Citizen joins a class by scanning its QR code."""

    qr_token: str = Field(min_length=8, max_length=128, description="Mã trong QR của lớp")
    display_name: str = Field(
        min_length=1,
        max_length=DISPLAY_NAME_MAX,
        description="Biệt danh hoặc mã học viên do tình nguyện viên cấp (không phải họ tên thật)",
    )
    accent_pref: AccentPref | None = Field(
        default=None, description="Giọng ưa thích: bac/trung/nam"
    )


class LoginRequest(RequestModel):
    """Volunteer/officer login."""

    username: str = Field(min_length=1, max_length=64, description="Tên đăng nhập")
    password: str = Field(min_length=1, max_length=128, description="Mật khẩu")


class TokenResponse(ResponseModel):
    """A short-lived JWT plus the identity it encodes."""

    token: str = Field(description="JWT (HS256) gửi trong header Authorization: Bearer")
    user_id: str = Field(
        description="Mã người dùng (UUID; chế độ demo: demo-citizen-xxxxxxxx hoặc demo-officer)"
    )
    role: Role = Field(description="Vai: citizen | volunteer | officer")


# ---------------------------------------------------------------- classes & reports
class ClassCreate(RequestModel):
    """Volunteer creates a class."""

    name: str = Field(min_length=1, max_length=120, description="Tên lớp")
    ward_code: str = Field(
        min_length=1, max_length=16, description="Mã phường/xã theo danh mục hành chính 2026"
    )


class ClassOut(ResponseModel):
    """A created class with its QR join link."""

    class_id: str = Field(description="Mã lớp (UUID)")
    qr_url: str = Field(description="Đường dẫn vào lớp để in thành mã QR")
    qr_token: str = Field(description="Mã trong QR (có hạn, thu hồi được)")


class ProgressRow(ResponseModel):
    """Progress of one learner."""

    user_id: str = Field(description="Mã học viên")
    display_name: str = Field(description="Biệt danh/mã học viên")
    scenarios_done: int = Field(ge=0, description="Số bài đã hoàn thành")
    success_rate: float = Field(ge=0, le=1, description="Tỷ lệ phiên thành công")
    mistakes: int = Field(ge=0, description="Tổng số bước sai")
    hints_used: int = Field(ge=0, description="Tổng số lần cần gợi ý")
    last_active: datetime | None = Field(default=None, description="Lần hoạt động gần nhất (UTC)")


class CoachingSuggestion(ResponseModel):
    """A learner the volunteer should coach one-on-one today."""

    user_id: str = Field(description="Mã học viên")
    display_name: str = Field(description="Biệt danh/mã học viên")
    reason: str = Field(description="Lý do cần kèm riêng (tiếng Việt)")


class ClassProgress(ResponseModel):
    """Progress table for a class plus the coaching shortlist."""

    rows: list[ProgressRow] = Field(default_factory=list, description="Tiến độ từng học viên")
    needs_coaching: list[CoachingSuggestion] = Field(
        default_factory=list, description="Học viên cần kèm riêng hôm nay"
    )


ReportFormat = Literal["pdf", "xlsx"]


# ---------------------------------------------------------------- scenarios & sessions
class ScenarioSummary(ResponseModel):
    """One sandbox scenario as listed by ``GET /v1/scenarios``."""

    id: str = Field(pattern=SLUG_PATTERN, description="Mã kịch bản (slug)")
    skill_group: str = Field(description="Nhóm kỹ năng (config/app.yaml: skill_groups)")
    level: int = Field(ge=1, le=3, description="Mức độ 1..3")
    goal: str = Field(description="Mục tiêu bài học, nói với người dân")
    version: str = Field(description="Phiên bản kịch bản")


class SessionCreate(RequestModel):
    """Start a sandbox session."""

    scenario_id: str = Field(pattern=SLUG_PATTERN, max_length=64, description="Mã kịch bản")


class SessionOut(ResponseModel):
    """A started session and its first screen."""

    session_id: str = Field(description="Mã phiên (UUID)")
    screen: dict[str, Any] = Field(description="Màn hình đầu tiên (theo schema sandbox)")


class SessionEvent(RequestModel):
    """An action from the learner inside the sandbox."""

    type: Literal["tap", "input", "ask", "back"] = Field(description="Loại hành động")
    target: str | None = Field(default=None, max_length=64, description="Mã phần tử/ô nhập")
    value: str | None = Field(default=None, max_length=500, description="Giá trị nhập hoặc câu hỏi")


class SessionEventOut(ResponseModel):
    """One SSE frame: new sandbox state plus the coach line."""

    state: dict[str, Any] = Field(description="Trạng thái mới của phiên")
    say: str = Field(description="Câu huấn luyện viên nói (≤ 2 câu)")


# ---------------------------------------------------------------- speech
class AsrOut(ResponseModel):
    """Speech-to-text result."""

    text: str = Field(description="Văn bản nhận dạng")
    confidence: float = Field(ge=0, le=1, description="Độ tin cậy 0..1")
    accent_tag: AccentPref | None = Field(default=None, description="Giọng nhận ra: bac/trung/nam")


class TtsIn(RequestModel):
    """Text to speak."""

    text: str = Field(min_length=1, max_length=TTS_TEXT_MAX, description="Văn bản cần đọc")


class TtsOut(ResponseModel):
    """Synthesised audio location."""

    audio_url: str = Field(description="Đường dẫn file âm thanh")
    cached: bool = Field(description="Đã có sẵn trong bộ nhớ tạm")


# ---------------------------------------------------------------- coach
class AskIn(RequestModel):
    """A question for the grounded coach."""

    question: str = Field(
        min_length=1, max_length=QUESTION_MAX, description="Câu hỏi của người dân"
    )
    session_id: str | None = Field(
        default=None, max_length=SESSION_ID_MAX, description="Mã phiên đang tập (nếu có)"
    )


class Citation(ResponseModel):
    """A source backing the answer."""

    doc_id: str = Field(description="Mã tài liệu trong kho hướng dẫn")
    title: str = Field(description="Tên tài liệu")
    url: str = Field(description="Đường dẫn trang chính thống")
    quote: str | None = Field(default=None, description="Đoạn trích ngắn")
    agency: str | None = Field(default=None, description="Cơ quan ban hành / công bố trang nguồn")
    source_portal: str | None = Field(default=None, description="Cổng thông tin chứa trang nguồn")
    fetched_at: datetime | None = Field(
        default=None, description="Thời điểm CTCV đọc trang nguồn (UTC)"
    )
    effective_date: date | None = Field(
        default=None, description="Ngày hiệu lực (chỉ khi nguồn có công bố)"
    )
    section: str | None = Field(
        default=None, description="Mục của thủ tục, ví dụ phi_le_phi, thanh_phan_ho_so"
    )
    procedure_id: str | None = Field(default=None, description="Mã thủ tục hành chính")


# Closed vocabularies come from the agent contracts (ADR-007 C4) so they cannot drift.
AskReason = Reason
# ``llm_unverified`` exists only for the evaluation ablation and is never served (C6).
ServedAnswerMode = Literal["llm_verified", "template", "safety", "no_source"]


class ProcedureRefOut(ResponseModel):
    """Short reference to an administrative procedure and its official page."""

    procedure_id: str = Field(description="Mã thủ tục (mã quốc gia hoặc bca-<matt>)")
    ten: str = Field(description="Tên thủ tục")
    co_quan: str | None = Field(default=None, description="Cơ quan thực hiện")
    source_url: str = Field(description="Trang gốc trên cổng dịch vụ công")
    fetched_at: datetime = Field(description="Thời điểm CTCV đọc trang gốc (UTC)")


class DocItemOut(ResponseModel):
    """One document to prepare."""

    doc_key: str = Field(description="Mã giấy tờ trong thủ tục: d01, d02…")
    name: str = Field(description="Tên giấy tờ")
    case_label: str | None = Field(default=None, description="Trường hợp áp dụng (nếu có)")
    originals: int | None = Field(default=None, description="Số bản chính")
    copies: int | None = Field(default=None, description="Số bản sao")
    form_code: str | None = Field(default=None, description="Mã mẫu đơn, tờ khai (nếu có)")


class FeeItemOut(ResponseModel):
    """Fee and time limit of one way of submitting."""

    channel: Channel = Field(description="Cách nộp: truc_tiep | truc_tuyen | buu_chinh | khac")
    channel_text: str = Field(description="Cách nộp như trang gốc ghi")
    time_limit: str | None = Field(default=None, description="Thời hạn giải quyết")
    fee_text: str | None = Field(default=None, description="Phí, lệ phí như trang gốc ghi")
    amounts_vnd: list[int] = Field(
        default_factory=list, description="Các mức tiền (đồng) chép từ trang gốc"
    )


class ProcedureCardOut(ProcedureRefOut):
    """Procedure card shown under the answer: documents, fees and cases."""

    documents: list[DocItemOut] = Field(default_factory=list, description="Giấy tờ cần chuẩn bị")
    fees: list[FeeItemOut] = Field(
        default_factory=list, description="Phí và thời hạn theo cách nộp"
    )
    cases: list[str] = Field(default_factory=list, description="Các trường hợp của thủ tục")


class AskOut(ResponseModel):
    """A grounded answer (internal diagnostics are never part of it)."""

    answer: str = Field(description="Câu trả lời (≤ 2 câu)")
    citations: list[Citation] = Field(default_factory=list, description="Nguồn trích dẫn")
    confidence: float = Field(ge=0, le=1, description="Độ tin cậy 0..1")
    escalate: bool = Field(description="Cần chuyển cho tình nguyện viên")
    refused: bool = Field(default=False, description="Từ chối vì câu hỏi không an toàn")
    reason: AskReason = Field(default="ok", description="Lý do: ok, no_source, sensitive…")
    answer_mode: ServedAnswerMode = Field(
        description="Cách tạo câu: llm_verified | template | safety | no_source"
    )
    procedure: ProcedureCardOut | None = Field(
        default=None, description="Thẻ thủ tục (giấy tờ, phí) khi trả lời được"
    )


def _no_duplicates(values: list[str]) -> list[str]:
    """Reject a list with repeated entries."""
    if len(values) != len(set(values)):
        raise ValueError("danh sách giấy tờ đã nhận có mã bị trùng")
    return values


DocKey = Annotated[str, Field(pattern=DOC_KEY_PATTERN)]


class IntakeCheckIn(RequestModel):
    """Officer checklist request: exactly one of ``procedure_id`` and ``query``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    procedure_id: str | None = Field(
        default=None,
        max_length=PROCEDURE_ID_MAX,
        pattern=PROCEDURE_ID_PATTERN,
        description="Mã thủ tục (chọn từ kết quả tìm)",
    )
    query: str | None = Field(
        default=None,
        min_length=QUERY_MIN,
        max_length=QUERY_MAX,
        description="Tên thủ tục cần tìm, ví dụ: đăng ký tạm trú",
    )
    received: Annotated[
        list[DocKey], Field(max_length=RECEIVED_MAX), AfterValidator(_no_duplicates)
    ] = Field(default_factory=list, description="Mã các giấy tờ đã nhận (d01, d02…)")
    case_label: str | None = Field(
        default=None, max_length=CASE_LABEL_MAX, description="Trường hợp của hồ sơ (nếu có)"
    )

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        """Require exactly one of ``procedure_id`` and ``query``."""
        if (self.procedure_id is None) == (self.query is None):
            raise ValueError("cần đúng một trong hai: procedure_id hoặc query")
        return self


class ChecklistItemOut(DocItemOut):
    """A document of the checklist with its status."""

    status: ChecklistStatus = Field(
        description="da_nhan (đã nhận), thieu (còn thiếu) hoặc neu_ap_dung (chỉ cần khi áp dụng)"
    )


class IntakeCheckOut(ResponseModel):
    """Officer checklist: what is missing and a short message for the citizen."""

    procedure: ProcedureRefOut = Field(description="Thủ tục đang kiểm")
    alternatives: list[ProcedureRefOut] = Field(
        default_factory=list, description="Thủ tục gần giống (tối đa 3)"
    )
    cases: list[str] = Field(default_factory=list, description="Các trường hợp của thủ tục")
    needs_case: bool = Field(description="Cần chọn trường hợp trước khi kiểm đủ")
    items: list[ChecklistItemOut] = Field(default_factory=list, description="Danh mục giấy tờ")
    missing_count: int = Field(ge=0, description="Số giấy tờ còn thiếu")
    message_for_citizen: str = Field(description="Câu nói với người dân (≤ 2 câu)")
    citations: list[Citation] = Field(default_factory=list, description="Nguồn của danh mục")


class Box(ResponseModel):
    """A detected UI element on a screenshot."""

    element_id: str = Field(description="Mã phần tử trong catalog")
    label: str = Field(description="Nhãn hiển thị")
    x: int = Field(ge=0, description="Tọa độ x (px)")
    y: int = Field(ge=0, description="Tọa độ y (px)")
    w: int = Field(ge=0, description="Chiều rộng (px)")
    h: int = Field(ge=0, description="Chiều cao (px)")
    confidence: float = Field(ge=0, le=1, description="Độ tin cậy 0..1")


class ScreenOut(ResponseModel):
    """Next step derived from a screenshot."""

    screen_state: str = Field(description="Mã màn hình trong catalog (D28)")
    step_text: str = Field(description="Bước tiếp theo, nói với người dân")
    boxes: list[Box] = Field(default_factory=list, description="Vùng cần bấm")


# ---------------------------------------------------------------- drills
class DrillStart(RequestModel):
    """Start a scam drill; the server picks the variant."""

    scenario_key: str | None = Field(
        default=None, pattern=SLUG_PATTERN, max_length=64, description="Mã kịch bản (tùy chọn)"
    )


class DrillOption(ResponseModel):
    """A choice shown to the learner (correctness is never sent to the client)."""

    id: str = Field(description="Mã lựa chọn")
    text: str = Field(description="Nội dung lựa chọn")


class DrillScenarioView(ResponseModel):
    """The client-facing part of a drill scenario (labelled as a simulation)."""

    key: str = Field(description="Mã kịch bản")
    channel: Literal["sms", "zalo", "call"] = Field(description="Kênh giả lập")
    impersonates: str = Field(description="Đối tượng bị mạo danh (nhãn)")
    pretext: str = Field(description="Tình huống (1 câu)")
    utterance: str = Field(description="Một lượt thoại mô phỏng, có nhãn [Mô phỏng]")
    options: list[DrillOption] = Field(description="3–4 lựa chọn")
    label: str = Field(description="Nhãn bắt buộc: Đây là mô phỏng")


class DrillOut(ResponseModel):
    """A started drill."""

    drill_id: str = Field(description="Mã lượt tập (UUID)")
    scenario: DrillScenarioView = Field(description="Kịch bản hiển thị")


class DrillAnswer(RequestModel):
    """The learner's choice."""

    option_id: str = Field(min_length=1, max_length=32, description="Mã lựa chọn")


class DrillResult(ResponseModel):
    """Score and debrief for a drill attempt."""

    score: int = Field(ge=0, le=100, description="Điểm 0..100")
    red_flags: list[str] = Field(default_factory=list, description="Dấu hiệu lừa đảo đã gặp")
    debrief: str = Field(description="Giải thích ngắn (≤ 2 câu)")
    three_things: list[str] = Field(
        min_length=THREE_THINGS, max_length=THREE_THINGS, description="Ba điều cần nhớ"
    )


# ---------------------------------------------------------------- system
CheckStatus = Literal["ok", "error", "skipped"]


class HealthOut(ResponseModel):
    """Service health."""

    status: Literal["ok", "degraded"] = Field(description="ok khi không kiểm tra nào lỗi")
    version: str = Field(description="Phiên bản ctcv-api")
    checks: dict[str, CheckStatus] = Field(description="Kết quả từng kiểm tra: db, redis, qdrant")
