"""Contracts of the TTHC knowledge base (ADR-007 C2–C4): records, chunks, hits and errors.

``ProcedureRecord`` mirrors ``config/schemas/tthc-record.schema.json`` field for field; both
reject unknown keys at every level. ``Chunk`` is one cited passage produced by
``ctcv_agent.rag.chunker``; ``KnowledgeBase`` is the read-only protocol that the answer
engine, the intake checker and the ``search_guides`` tool backend depend on.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal, Protocol, get_args, runtime_checkable

from pydantic import AfterValidator, AwareDatetime, Field

from ctcv_agent.schemas import Citation, ProcedureId, StrictModel
from ctcv_core.errors import AppError

Section = Literal[
    "tong_quan",
    "trinh_tu",
    "thanh_phan_ho_so",
    "phi_le_phi",
    "thoi_han",
    "dieu_kien",
    "can_cu_phap_ly",
    "bieu_mau",
]
SECTIONS: tuple[str, ...] = get_args(Section)
SECTION_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "tong_quan": "Thông tin chung",
        "trinh_tu": "Trình tự thực hiện",
        "thanh_phan_ho_so": "Thành phần hồ sơ",
        "phi_le_phi": "Phí, lệ phí",
        "thoi_han": "Thời hạn và cách thức nộp",
        "dieu_kien": "Yêu cầu, điều kiện",
        "can_cu_phap_ly": "Căn cứ pháp lý",
        "bieu_mau": "Biểu mẫu",
    }
)
Channel = Literal["truc_tiep", "truc_tuyen", "buu_chinh", "khac"]
Level = Literal["bo", "tinh", "xa"]
RECORD_SCHEMA_VERSION = 1
PARSER_VERSION = "tthc-bca/1"
DOC_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
DOC_ID_MAX = 64
_CITATION_TITLE_MAX = 200
_CITATION_QUOTE_MAX = 500


def _require_utc(value: datetime) -> datetime:
    """Accept only timestamps whose UTC offset is zero (C2: ``date-time`` with ``Z``)."""
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("thời điểm phải là giờ UTC (hậu tố Z)")
    return value


Text = Annotated[str, Field(min_length=1)]
DocKey = Annotated[str, Field(pattern=r"^d\d{2}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
HttpsUrl = Annotated[str, Field(pattern=r"^https://\S+$")]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]
Count = Annotated[int, Field(ge=0)]
ChunkId = Annotated[str, Field(min_length=1, max_length=DOC_ID_MAX, pattern=DOC_ID_PATTERN)]
SectionLabel = Annotated[str, Field(min_length=1, max_length=200)]
SectionText = Annotated[str, Field(max_length=8000)]


class CachThuc(StrictModel):
    """One submission channel with its time limit and fee (C2 ``cach_thuc``)."""

    kenh: Channel
    kenh_text: str = Field(min_length=1, max_length=200)
    thoi_han: Text | None = None
    phi_le_phi: Text | None = None
    phi_vnd: list[Count] = Field(default_factory=list)
    mo_ta: Text | None = None


class DocumentItem(StrictModel):
    """One required document (C2 ``thanh_phan_ho_so``); ``doc_key`` is d01, d02… in page order."""

    doc_key: DocKey
    truong_hop: Text | None = None
    ten_giay_to: str = Field(min_length=1, max_length=600)
    ban_chinh: Count | None = None
    ban_sao: Count | None = None
    mau: Text | None = None


class LegalRef(StrictModel):
    """A legal basis entry (C2 ``can_cu_phap_ly``)."""

    so_hieu: Text | None = None
    ten: Text


class FormRef(StrictModel):
    """A downloadable form (C2 ``bieu_mau``); only https links are kept."""

    ten: Text
    url: HttpsUrl


class RecordMeta(StrictModel):
    """Provenance of a record: page, publisher, crawl time, hashes and parser version."""

    source_url: HttpsUrl
    source_portal: str = Field(min_length=1, max_length=200)
    agency: str = Field(min_length=1, max_length=200)
    matt: str = Field(pattern=r"^\d+$")
    linh_vuc_code: Text | None = None
    fetched_at: UtcDatetime
    sha256_raw: Sha256
    sha256_content: Sha256
    updated_at: date | None = None
    effective_date: date | None = None
    license_note: str = Field(min_length=1, max_length=500)
    parser_version: Literal["tthc-bca/1"]


def content_sha256_of(record: Mapping[str, Any]) -> str:
    """Return the C2 content hash of a record mapping (every key except ``meta``)."""
    body = {key: value for key, value in record.items() if key != "meta"}
    blob = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ProcedureRecord(StrictModel):
    """Administrative procedure record v1 (ADR-007 C2)."""

    schema_version: Literal[1]
    procedure_id: ProcedureId
    ma_thu_tuc: Text | None = None
    ten: str = Field(min_length=1, max_length=300)
    linh_vuc: Text | None = None
    co_quan_thuc_hien: Text | None = None
    cap_thuc_hien: Level | None = None
    muc_do_dvc: Text | None = None
    doi_tuong: Text | None = None
    cach_thuc: list[CachThuc] = Field(default_factory=list)
    trinh_tu: list[Text] = Field(default_factory=list)
    thanh_phan_ho_so: list[DocumentItem] = Field(default_factory=list)
    yeu_cau_dieu_kien: Text | None = None
    can_cu_phap_ly: list[LegalRef] = Field(default_factory=list)
    bieu_mau: list[FormRef] = Field(default_factory=list)
    ket_qua: Text | None = None
    sections_raw: dict[SectionLabel, SectionText] = Field(default_factory=dict)
    meta: RecordMeta

    @classmethod
    def load(cls, path: Path | str) -> ProcedureRecord:
        """Read and validate one ``<procedure_id>.json`` file (UTF-8)."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def content_sha256(self) -> str:
        """Hash of the record without ``meta``; equals ``meta.sha256_content`` when unchanged."""
        return content_sha256_of(self.model_dump(mode="json", exclude={"meta"}))


def _clip(text: str, limit: int) -> str:
    """Shorten ``text`` to ``limit`` characters, ending with an ellipsis when cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class Chunk(StrictModel):
    """One retrievable, citable passage of a procedure (C3)."""

    doc_id: ChunkId
    procedure_id: ProcedureId
    section: Section
    part: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=400)
    text: str = Field(min_length=1)
    url: HttpsUrl
    agency: Text | None = None
    source_portal: Text | None = None
    fetched_at: UtcDatetime
    effective_date: date | None = None
    skill: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    sha256_content: Sha256

    def to_citation(self, quote: str = "") -> Citation:
        """Build the :class:`~ctcv_agent.schemas.Citation` shown to the citizen."""
        return Citation(
            doc_id=self.doc_id,
            url=self.url,
            title=_clip(self.title, _CITATION_TITLE_MAX),
            effective_date=self.effective_date,
            quote=_clip(quote, _CITATION_QUOTE_MAX),
            agency=self.agency,
            source_portal=self.source_portal,
            fetched_at=self.fetched_at,
            section=self.section,
            procedure_id=self.procedure_id,
        )


class Hit(StrictModel):
    """A ranked search hit: fused (RRF) score plus the lexical and dense components."""

    chunk: Chunk
    score: float
    bm25_score: float = 0.0
    dense_score: float | None = None
    rank: int = Field(ge=1)


class SearchResult(StrictModel):
    """Hits in rank order; ``degraded`` is True when dense retrieval was unavailable."""

    hits: list[Hit] = Field(default_factory=list)
    degraded: bool = False


@runtime_checkable
class KnowledgeBase(Protocol):
    """Read-only access to procedure records and their chunks."""

    def search(
        self,
        query: str,
        top_k: int,
        *,
        procedure_id: str | None = None,
        sections: Sequence[str] | None = None,
    ) -> SearchResult:
        """Return the best ``top_k`` hits, optionally restricted to a procedure/sections."""
        ...

    def get_procedure(self, pid: str) -> ProcedureRecord | None:
        """Return the record with this ``procedure_id`` or None."""
        ...

    def get_chunk(self, doc_id: str) -> Chunk | None:
        """Return the chunk with this ``doc_id`` or None."""
        ...

    def chunks_for(self, pid: str, sections: Sequence[str] | None = None) -> list[Chunk]:
        """Return a procedure's chunks in chunker order, optionally filtered by section."""
        ...

    def find_procedures(self, query: str, limit: int) -> list[tuple[ProcedureRecord, float]]:
        """Return up to ``limit`` distinct procedures with their best hit score, best first."""
        ...

    def procedure_count(self) -> int:
        """Return how many procedure records are loaded."""
        ...


class _KnowledgeBaseError(AppError):
    """Base for KB errors: fixed code, status and Vietnamese message; reason goes to details."""

    CODE = "KB_ERROR"
    STATUS = 500
    MESSAGE = "Có lỗi khi tra kho thủ tục, bác thử lại sau nhé."

    def __init__(self, reason: str | None = None, *, details: dict[str, Any] | None = None):
        """Create the error; ``reason`` (never PII) is stored as ``details["reason"]``."""
        merged = dict(details or {})
        if reason:
            merged["reason"] = reason
        super().__init__(self.CODE, self.MESSAGE, self.STATUS, merged or None)


class KnowledgeBaseNotReady(_KnowledgeBaseError):  # noqa: N818 — name fixed by ADR-007 C4
    """503 — the index is missing, stale or built with another embedding model."""

    CODE = "KB_NOT_READY"
    STATUS = 503
    MESSAGE = "Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé."


class ProcedureNotFound(_KnowledgeBaseError):  # noqa: N818 — name fixed by ADR-007 C4
    """404 — no procedure matches the given id or query."""

    CODE = "PROCEDURE_NOT_FOUND"
    STATUS = 404
    MESSAGE = "Chưa tìm thấy thủ tục này trong kho, anh/chị thử gõ tên khác nhé."
