"""Answer and intake contracts (ADR-007 C4) shared by the engine, the API and evaluation.

``AskResult`` is what :class:`AnswerService` returns for one citizen question; the API maps
it to ``AskOut`` and never exposes ``diagnostics`` (C6). ``IntakeRequest``/``IntakeResult``
are the officer-side document checklist (no LLM). Every model forbids unknown fields.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import AfterValidator, AwareDatetime, Field, model_validator

from ctcv_agent.rag.types import CachThuc, Channel, DocumentItem, ProcedureRecord
from ctcv_agent.schemas import Citation, ProcedureId, SessionContext, StrictModel
from ctcv_core.config import load_config
from ctcv_core.text import count_sentences

Reason = Literal[
    "ok",
    "no_source",
    "sensitive",
    "real_action",
    "pasted_content",
    "verify_failed",
    "kb_not_ready",
]
AnswerMode = Literal["llm_verified", "llm_unverified", "template", "safety", "no_source"]
# ``neu_ap_dung``: a document needed only in a sub-case its name states ("Trường hợp người
# Việt Nam định cư ở nước ngoài … thì …"); not received, but not counted as missing either.
ChecklistStatus = Literal["da_nhan", "thieu", "neu_ap_dung"]
TIMING_KEYS = frozenset({"retrieve", "compose", "verify", "total"})
MAX_RETRIEVED = 5
MAX_RECEIVED = 60
MAX_ALTERNATIVES = 3
# Case labels are copied from the record (``truong_hop``); the longest real one (1.004222) has
# 918 characters, so the request accepts what the checker itself returns (red-team F-09).
MAX_CASE_LABEL = 2000

DocKey = Annotated[str, Field(pattern=r"^d\d{2}$")]
Score = Annotated[float, Field(ge=0.0, le=1.0)]


def _unique(values: list[str]) -> list[str]:
    """Reject duplicate entries."""
    if len(values) != len(set(values)):
        raise ValueError("danh sách có phần tử trùng")
    return values


def _within_sentence_limit(text: str) -> str:
    """Reject citizen-facing text longer than ``guardrails.max_sentences``."""
    limit = int(load_config("guardrails")["max_sentences"])
    if count_sentences(text) > limit:
        raise ValueError(f"tin nhắn cho người dân dài quá {limit} câu")
    return text


class ProcedureRef(StrictModel):
    """Short reference to a procedure with its official page and crawl time."""

    procedure_id: ProcedureId
    ten: str = Field(min_length=1, max_length=300)
    co_quan: str | None = None
    source_url: str = Field(pattern=r"^https://\S+$")
    fetched_at: AwareDatetime

    @classmethod
    def from_record(cls, record: ProcedureRecord) -> Self:
        """Build the reference from a record (``co_quan`` = ``co_quan_thuc_hien``)."""
        return cls(**_ref_fields(record))


def _ref_fields(record: ProcedureRecord) -> dict[str, object]:
    return {
        "procedure_id": record.procedure_id,
        "ten": record.ten,
        "co_quan": record.co_quan_thuc_hien,
        "source_url": record.meta.source_url,
        "fetched_at": record.meta.fetched_at,
    }


class DocItem(StrictModel):
    """One document to bring, as shown on the citizen card and the officer checklist."""

    doc_key: DocKey
    name: str = Field(min_length=1, max_length=600)
    case_label: str | None = None
    originals: int | None = Field(default=None, ge=0)
    copies: int | None = Field(default=None, ge=0)
    form_code: str | None = None

    @classmethod
    def from_document(cls, item: DocumentItem) -> Self:
        """Map a record document (C2 names) to the display names of C4."""
        return cls(
            doc_key=item.doc_key,
            name=item.ten_giay_to,
            case_label=item.truong_hop,
            originals=item.ban_chinh,
            copies=item.ban_sao,
            form_code=item.mau,
        )


class FeeItem(StrictModel):
    """Fee and time limit of one submission channel."""

    channel: Channel
    channel_text: str = Field(min_length=1, max_length=200)
    time_limit: str | None = None
    fee_text: str | None = None
    amounts_vnd: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list)

    @classmethod
    def from_cach_thuc(cls, item: CachThuc) -> Self:
        """Map a record channel (C2 names) to the display names of C4."""
        return cls(
            channel=item.kenh,
            channel_text=item.kenh_text,
            time_limit=item.thoi_han,
            fee_text=item.phi_le_phi,
            amounts_vnd=list(item.phi_vnd),
        )


class ProcedureCard(ProcedureRef):
    """Procedure reference plus documents, fees and the list of cases (trường hợp)."""

    documents: list[DocItem] = Field(default_factory=list)
    fees: list[FeeItem] = Field(default_factory=list)
    cases: list[str] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: ProcedureRecord) -> Self:
        """Build the full card; ``cases`` keeps first-seen order of distinct ``truong_hop``."""
        docs = record.thanh_phan_ho_so
        return cls(
            **_ref_fields(record),
            documents=[DocItem.from_document(d) for d in docs],
            fees=[FeeItem.from_cach_thuc(c) for c in record.cach_thuc],
            cases=list(dict.fromkeys(d.truong_hop for d in docs if d.truong_hop)),
        )


def _check_timings(timings: dict[str, float]) -> dict[str, float]:
    unknown = set(timings) - TIMING_KEYS
    if unknown:
        raise ValueError(f"khóa thời gian không hợp lệ: {sorted(unknown)}")
    if any(value < 0 for value in timings.values()):
        raise ValueError("thời gian phải ≥ 0")
    return timings


class AskDiagnostics(StrictModel):
    """Internal trace of one answer (eval and logs only, never returned by the API)."""

    intent: str | None = None
    retrieved_procedure_ids: Annotated[
        list[str], Field(max_length=MAX_RETRIEVED), AfterValidator(_unique)
    ] = Field(default_factory=list)
    top_dense: float | None = None  # cosine similarity, may be slightly outside 0..1
    match_score: Score | None = None
    gate_passed: bool = False
    answer_core: str | None = None
    composer_sentence: str | None = None
    composer_doc_ids: list[str] = Field(default_factory=list)
    composer_error: str | None = None
    fallback_reason: str | None = None
    degraded: bool = False
    timings_ms: Annotated[dict[str, float], AfterValidator(_check_timings)] = Field(
        default_factory=dict
    )
    hosts_contacted: list[str] = Field(default_factory=list)


class AskResult(StrictModel):
    """Answer to one citizen question with citations, confidence and escalation flag."""

    answer: str = Field(min_length=1, max_length=800)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Score
    escalate: bool
    refused: bool = False
    reason: Reason
    answer_mode: AnswerMode
    procedure: ProcedureCard | None = None
    diagnostics: AskDiagnostics = Field(default_factory=AskDiagnostics)


class IntakeRequest(StrictModel):
    """Officer checklist request: exactly one of ``procedure_id`` and ``query``."""

    procedure_id: ProcedureId | None = None
    query: str | None = Field(default=None, min_length=2, max_length=200)
    received: Annotated[list[DocKey], Field(max_length=MAX_RECEIVED), AfterValidator(_unique)] = (
        Field(default_factory=list)
    )
    case_label: str | None = Field(default=None, max_length=MAX_CASE_LABEL)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        if (self.procedure_id is None) == (self.query is None):
            raise ValueError("cần đúng một trong hai: procedure_id hoặc query")
        return self


class ChecklistItem(DocItem):
    """A document of the checklist with its status (received, missing or only-if-applicable)."""

    status: ChecklistStatus


class IntakeResult(StrictModel):
    """Checklist outcome: what is missing and a ≤ 2-sentence message for the citizen."""

    procedure: ProcedureRef
    alternatives: list[ProcedureRef] = Field(default_factory=list, max_length=MAX_ALTERNATIVES)
    cases: list[str] = Field(default_factory=list)
    needs_case: bool = False
    items: list[ChecklistItem] = Field(default_factory=list)
    missing_count: int = Field(ge=0)
    message_for_citizen: Annotated[
        str, Field(min_length=1, max_length=400), AfterValidator(_within_sentence_limit)
    ]
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _missing_count_matches_items(self) -> Self:
        missing = sum(1 for item in self.items if item.status == "thieu")
        if self.missing_count != missing:
            raise ValueError(f"missing_count={self.missing_count} nhưng có {missing} mục thiếu")
        return self


@runtime_checkable
class AnswerService(Protocol):
    """Answers one citizen question about an administrative procedure."""

    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        """Return a cited answer, a safety line or a "not sure" escalation."""
        ...


@runtime_checkable
class IntakeService(Protocol):
    """Builds the officer's document checklist."""

    def check(self, req: IntakeRequest) -> IntakeResult:
        """Return received/missing documents for the requested procedure."""
        ...
