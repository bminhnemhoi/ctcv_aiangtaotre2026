"""Officer-side document checklist for a procedure (ADR-007 C4/C6, no LLM, no storage).

:class:`IntakeChecker` implements :class:`~ctcv_agent.contracts.IntakeService`: it finds the
procedure (by id, or the best match of a free-text query plus up to three alternatives),
lists the documents that apply (common ones, plus those of the chosen case), marks what the
officer has received and writes a ≤ 2-sentence message the officer can read to the citizen.
Everything is copied from the record; the citations point at its document-list chunks.

A document whose name itself states a sub-case ("Trường hợp người Việt Nam định cư ở nước
ngoài … thì sử dụng Tờ khai … (mẫu CT02)", "Đối với Quân đội nhân dân: …") is only needed
when that case applies: when not received it gets ``neu_ap_dung``, is not counted as missing
and is not named in the message (orchestrator live test 25/9, real 1.004222 d02). The query
is PII-redacted before it reaches the embedder, like a citizen question.
"""

from __future__ import annotations

import re

from ctcv_agent.answer_templates import (
    citation_quote,
    lower_first,
    replace_banned_terms,
    short_doc_name,
)
from ctcv_agent.contracts import (
    MAX_ALTERNATIVES,
    ChecklistItem,
    DocItem,
    IntakeRequest,
    IntakeResult,
    ProcedureRef,
)
from ctcv_agent.guardrails import redact_pii, rules
from ctcv_agent.rag.types import DocumentItem, KnowledgeBase, ProcedureNotFound, ProcedureRecord
from ctcv_agent.schemas import Citation
from ctcv_core.errors import ValidationFailed
from ctcv_core.text import count_sentences

MAX_NAMES_IN_MESSAGE = 3  # C4: the message names at most three missing documents
NAME_MAX_CHARS = 60  # C4: each name is cut at 60 characters
_TEN_MAX_CHARS = 120
_SECTION = "thanh_phan_ho_so"
# A name that opens with a case ("Trường hợp …", "Nếu …", "Đối với …", "Riêng …").
_CONDITIONAL_NAME_RE = re.compile(r"^\W*(?:trường\s+hợp|nếu|đối\s+với|riêng)(?!\w)", re.IGNORECASE)
# Sentence stops and ellipses inside a short name would split the message into sentences.
_INNER_STOP_RE = re.compile(r"[.!?…]+")


def is_conditional(item: DocumentItem) -> bool:
    """True when the document's own name states the case it is needed in."""
    return _CONDITIONAL_NAME_RE.search(item.ten_giay_to) is not None


def _status(item: DocumentItem, received: set[str]) -> str:
    if item.doc_key in received:
        return "da_nhan"
    return "neu_ap_dung" if is_conditional(item) else "thieu"


def _short_name(item: DocumentItem) -> str:
    """Short spoken name of a document, with its form code, without inner sentence stops."""
    name = short_doc_name(item.ten_giay_to, NAME_MAX_CHARS)
    if item.mau and item.mau not in name:
        name = f"{name} (mẫu {item.mau})"
    name = short_doc_name(name, NAME_MAX_CHARS) if len(name) > NAME_MAX_CHARS else name
    return " ".join(_INNER_STOP_RE.sub(" ", name).split()).rstrip(" ,;:(")


def _ten(record: ProcedureRecord) -> str:
    return short_doc_name(lower_first(record.ten), _TEN_MAX_CHARS)


def _message(record: ProcedureRecord, missing: list[DocumentItem], needs_case: bool) -> str:
    """Message for the citizen (≤ 2 sentences, plain words)."""
    ten = _ten(record)
    if missing:
        names = "; ".join(_short_name(d) for d in missing[:MAX_NAMES_IN_MESSAGE])
        text = f"Hồ sơ {ten} còn thiếu: {names}. Bác bổ sung rồi nộp lại giúp cháu nhé."
        if count_sentences(text) > rules().max_sentences:  # a name the counter still splits
            text = (
                f"Hồ sơ {ten} còn thiếu {len(missing)} giấy tờ trong danh mục, "
                "bác bổ sung rồi nộp lại giúp cháu nhé."
            )
    elif needs_case:
        text = (
            f"Hồ sơ {ten} cần giấy tờ khác nhau tùy trường hợp, "
            "bác chờ cán bộ chọn đúng trường hợp để kiểm tra tiếp nhé."
        )
    elif not record.thanh_phan_ho_so:
        text = (
            f"Trang gốc chưa ghi danh mục giấy tờ của thủ tục {ten}, "
            "bác hỏi cán bộ một cửa giúp cháu nhé."
        )
    else:
        text = f"Hồ sơ {ten} đã đủ giấy tờ theo danh mục, bác chờ cán bộ kiểm tra nội dung nhé."
    return replace_banned_terms(text)


class IntakeChecker:
    """Document checklist over a :class:`~ctcv_agent.rag.types.KnowledgeBase`."""

    def __init__(self, kb: KnowledgeBase) -> None:
        """Keep the knowledge base; nothing is loaded here."""
        self.kb = kb

    def _find(self, req: IntakeRequest) -> tuple[ProcedureRecord, list[ProcedureRecord]]:
        """The requested procedure and, for a query, up to three alternatives."""
        if req.procedure_id is not None:
            record = self.kb.get_procedure(req.procedure_id)
            if record is None:
                raise ProcedureNotFound("unknown_procedure_id")
            return record, []
        found = self.kb.find_procedures(redact_pii(req.query or ""), MAX_ALTERNATIVES + 1)
        if not found:
            raise ProcedureNotFound("no_match")
        return found[0][0], [r for r, _ in found[1:]]

    def _citations(self, record: ProcedureRecord) -> list[Citation]:
        chunks = self.kb.chunks_for(record.procedure_id, [_SECTION])
        return [c.to_citation(citation_quote(c.text)) for c in chunks]

    def check(self, req: IntakeRequest) -> IntakeResult:
        """Return received/missing documents for the requested procedure.

        Raises:
            ProcedureNotFound: unknown id, or no procedure matches the query (404).
            ValidationFailed: ``case_label`` is not one of the procedure's cases (422).
        """
        record, alternatives = self._find(req)
        docs = record.thanh_phan_ho_so
        cases = list(dict.fromkeys(d.truong_hop for d in docs if d.truong_hop))
        if req.case_label is not None and req.case_label not in cases:
            raise ValidationFailed(
                "Trường hợp này không có trong danh mục của thủ tục, anh/chị chọn lại nhé.",
                code="CASE_NOT_FOUND",
            )
        applicable = [d for d in docs if d.truong_hop is None or d.truong_hop == req.case_label]
        received = set(req.received)
        items = [
            ChecklistItem(**DocItem.from_document(d).model_dump(), status=_status(d, received))
            for d in applicable
        ]
        missing = [d for d in applicable if _status(d, received) == "thieu"]
        needs_case = bool(cases) and req.case_label is None
        return IntakeResult(
            procedure=ProcedureRef.from_record(record),
            alternatives=[ProcedureRef.from_record(r) for r in alternatives],
            cases=cases,
            needs_case=needs_case,
            items=items,
            missing_count=len(missing),
            message_for_citizen=_message(record, missing, needs_case),
            citations=self._citations(record),
        )
