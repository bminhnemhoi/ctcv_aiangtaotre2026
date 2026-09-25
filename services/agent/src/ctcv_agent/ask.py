"""Verified answers to citizen questions about administrative procedures (ADR-007, DA940-01).

:class:`AnswerEngine` implements :class:`~ctcv_agent.contracts.AnswerService`. One question
goes through a fixed pipeline; every step can only make the answer *safer*:

1. safety — empty question → "chưa chắc"; request for OTP/password → fixed warning; request
   to act on a real account → fixed refusal; pasted message or link → fixed line + escalate;
2. ``redact_pii`` — nothing identifying reaches retrieval or the composer;
3. route — intent (:mod:`ctcv_agent.intents`), hybrid search, procedure of the first hit,
   gate: ``dense ≥ min_dense_score`` and (title/field overlap ≥ ``title_overlap_min`` or
   ``dense ≥ high_dense_score``); failing the gate → "chưa chắc" + escalate, no citation;
4. fee questions first read the fee wording (:func:`~ctcv_agent.answer_templates.fee_status`):
   no fee text → "chưa chắc" + escalate without calling the composer (never "miễn phí");
   suspicious amounts → the template that states no amount, escalated;
5. compose — the composer (no tool) proposes one sentence from ≤ ``context_chunks`` chunks;
   it is kept only if it is one sentence, in Latin script, free of unsafe requests and PII,
   says "free" only when every channel of the record says so, pairs each channel with that
   channel's amount, every number occurs in the cited chunks and its words are supported;
6. template — otherwise a deterministic sentence copied from the record
   (:mod:`ctcv_agent.answer_templates`), numbers checked once more;
7. answer = sentence + closing (≤ 2 sentences), citations with publisher and crawl time,
   confidence from dense score and overlap, escalate below ``guardrails.escalate_confidence``
   (or when the template says no value).

The question itself is never stored or logged. ``KnowledgeBaseNotReady`` from the knowledge
base propagates (the API answers 503). Mode ``llm_unverified`` (raw composer sentence, no
check) exists only for the evaluation ablation and must be requested explicitly.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

from ctcv_agent.answer_templates import (
    CLOSING_DEFAULT,
    CLOSING_DOCS,
    CONDITION_WORD_RE,
    DEADLINE_INTENT,
    NO_SOURCE_LINE,
    PASTED_LINE,
    REAL_ACTION_LINE,
    SENSITIVE_LINE,
    citation_quote,
    claims_free,
    clip_words,
    closing_for,
    common_documents,
    document_condition,
    fee_channel_mismatch,
    fee_expired,
    fee_status,
    fee_validity,
    render_template,
    replace_banned_terms,
    short_doc_name,
)
from ctcv_agent.compose import ComposeOutput, Composer, build_composer
from ctcv_agent.contracts import AskDiagnostics, AskResult, ProcedureCard, Reason
from ctcv_agent.guardrails import (
    contains_link,
    enforce_style,
    looks_like_pasted_content,
    redact_pii,
    refuses_real_action,
    refuses_sensitive_request,
    requires_citation,
    rules,
)
from ctcv_agent.intents import detect_intent, phrase_regex
from ctcv_agent.numeric import canonical_numbers, money_amounts, numbers_supported
from ctcv_agent.rag.query import (
    content_tokens,
    expand_synonyms,
    fold_accents,
    normalize_query,
    syllable_bigrams,
)
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import Chunk, KnowledgeBase, ProcedureRecord, SearchResult
from ctcv_agent.schemas import Citation, SessionContext
from ctcv_agent.verify import evaluate_sentence, has_foreign_script, tokenize
from ctcv_core.text import count_sentences

log = logging.getLogger(__name__)

MODES: tuple[str, ...] = ("llm_verified", "template_only", "llm_unverified")
MAX_RETRIEVED_IDS = 5
_ANSWER_MAX_CHARS = next(
    int(m.max_length) for m in AskResult.model_fields["answer"].metadata if hasattr(m, "max_length")
)
MAX_CORE_CHARS = _ANSWER_MAX_CHARS - max(len(CLOSING_DEFAULT), len(CLOSING_DOCS)) - 1
_ENDINGS = (".", "!", "?", "…")
_NO_VALUE_REASONS = frozenset({"fee_suspicious", "fee_expired"})
_PROCESSING_TIME_SECTION = "thoi_han"
# Composer sentences claiming the assistant already acted ("cháu đã nộp … cho bác rồi") or
# telling the citizen to hand over a secret ("đọc mã vừa nhận … cho cán bộ", "mang theo mã
# PIN"). Red-team IC-A09…A13: defence in depth behind the composer prompt.
_CLAIMED_ACT_RE = re.compile(
    r"(?<!\w)(?:cháu|tôi|em|mình)\s+(?:đã\s+|vừa\s+)?(?:nộp|gửi|đăng\s+nhập|đăng\s+ký|điền|"
    r"khai|thanh\s+toán|chuyển|bấm)(?:\s+\S+){0,10}?\s+(?:cho|giùm|giúp|hộ|thay)\s+"
    r"(?:bác|cô|chú|ông|bà|anh|chị|bạn)(?!\w)",
    re.IGNORECASE,
)
_SECRET_HANDOVER_RE = re.compile(
    r"(?<!\w)(?:đọc|gửi|nói|cung\s+cấp|báo|mang\s+theo|nhắn)\s+(?:\S+\s+){0,6}?"
    r"(?:mã\s+(?:otp|pin|xác\s+(?:thực|nhận)|vừa|nhận|gửi\s+về|\d+\s+số|số\s+vừa)|mật\s+khẩu"
    r"|số\s+thẻ|cvv)(?!\w)",
    re.IGNORECASE,
)
# Words that only introduce a case ("Trường hợp … thì hồ sơ còn có"), not its content.
_CASE_WORDS = frozenset({"trường", "hợp", "nếu", "đối", "hồ", "sơ", "còn"})
# One case clause: "trường hợp / nếu / đối với" up to the end of the clause, the line or the
# " — bản chính: 1" counts the chunker appends to each document line.
_CASE_CLAUSE_RE = re.compile(r"(?<!\w)(?:trường\s+hợp|nếu|đối\s+với)(?!\w)[^.;\n—]*", re.IGNORECASE)
# Level of government at the end of a procedure name ("(thực hiện tại cấp tỉnh)", "thực hiện
# tại Công an cấp xã", "tại Cục …"): 1 xã, 2 tỉnh, 3 bộ — checked in that order.
_LEVEL_TAIL_RE = re.compile(r"\s*\(thực hiện|\s+thực hiện tại|\s+tại (?:Công an|Cục|Phòng)")
_LEVELS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"(?<!\w)xã(?!\w)", re.IGNORECASE), 1),
    (re.compile(r"(?<!\w)(?:tỉnh|tinh)(?!\w)", re.IGNORECASE), 2),
    (re.compile(r"(?<!\w)(?:trung\s+ương|cục|bộ)(?!\w)", re.IGNORECASE), 3),
)
_CAP_LEVEL = {"xa": 1, "tinh": 2, "bo": 3}
_WORD_RE = re.compile(r"\w+")
_LEVEL_IN_QUESTION_RE = re.compile(
    r"(?<!\w)(?:xã|phường|tỉnh|trung\s+ương|cục|bộ\s+công\s+an)(?!\w)", re.IGNORECASE
)


@dataclass(frozen=True)
class RouteDecision:
    """Where a question goes: intent, procedure of the first hit, gate scores and verdict."""

    intent: str
    procedure_id: str | None
    dense: float
    match: float
    passed: bool


# ----------------------------------------------------------------------------- safety
def asks_real_action(text: str) -> bool:
    """Request to act on a real account for the citizen (kept name; see ``refuses_real_action``).

    v2: the "làm hộ chiếu" masking and the long-delegation check moved into
    :func:`ctcv_agent.guardrails.refuses_real_action`, so the coach refuses the same texts.
    """
    return refuses_real_action(text)


# ----------------------------------------------------------------------------- matching
@lru_cache(maxsize=32)
def _phrases_regex(phrases: tuple[str, ...]) -> re.Pattern[str]:
    """One alternation of accent-tolerant whole-word phrases, longest first."""
    ordered = sorted(set(phrases), key=len, reverse=True)
    return re.compile("|".join(f"(?:{phrase_regex(p).pattern})" for p in ordered), re.IGNORECASE)


def _question_tokens(question: str, s: RagSettings) -> list[str]:
    """Content tokens of the question once generic words and intent phrases are removed."""
    phrases = (*s.gate.generic_words, *(p for group in s.intents.values() for p in group))
    stripped = _phrases_regex(tuple(phrases)).sub(" ", normalize_query(question, s))
    tokens = (t for t in content_tokens(stripped) if len(t) > 1 or t.isdigit())
    return list(dict.fromkeys(tokens))


def _record_tokens(record: ProcedureRecord, s: RagSettings) -> tuple[set[str], set[str]]:
    """``(exact, accent-free)`` tokens of name + field + synonyms, with glued bigrams."""
    base = f"{record.ten} {record.linh_vuc or ''}"
    tokens = content_tokens(" ".join([base, *expand_synonyms(base, s)]))
    exact = set(tokens) | {b.replace("_", "") for b in syllable_bigrams(tokens)}
    return exact, {fold_accents(t) for t in exact}


def procedure_match_score(question: str, record: ProcedureRecord, s: RagSettings) -> float:
    """Share of the question's content tokens found in the procedure name, field or synonyms.

    An unaccented question token may match an accented record token; an accented one must
    match exactly. A question with no content token left scores 0.
    """
    wanted = _question_tokens(question, s)
    if not wanted:
        return 0.0
    exact, folded = _record_tokens(record, s)
    hits = sum(1 for t in wanted if t in exact or (fold_accents(t) == t and t in folded))
    return round(hits / len(wanted), 4)


def twin_key(record: ProcedureRecord) -> tuple[str, int | None]:
    """``(name without its level-of-government tail, level 1 xã / 2 tỉnh / 3 bộ | None)``.

    The level is read from the tail of the name, else from ``cap_thuc_hien``.
    """
    found = _LEVEL_TAIL_RE.search(record.ten)
    cut = found.start() if found else len(record.ten)
    base = " ".join(record.ten[:cut].casefold().split())
    tail = record.ten[cut:]
    for pattern, level in _LEVELS:
        if tail and pattern.search(tail):
            return base, level
    return base, _CAP_LEVEL.get(record.cap_thuc_hien or "")


def _local_twin(pid: str, result: SearchResult, kb: KnowledgeBase) -> str:
    """The most local retrieved procedure whose name equals ``pid``'s but for the level.

    Citizens apply at the commune or province; the central twin ("thực hiện tại cấp trung
    ương") only wins when the question names a level (checked by the caller).
    """
    record = kb.get_procedure(pid)
    if record is None:
        return pid
    base, best_level = twin_key(record)
    best = pid
    for other in dict.fromkeys(h.chunk.procedure_id for h in result.hits):
        candidate = kb.get_procedure(other)
        other_base, level = twin_key(candidate) if candidate is not None else ("", None)
        if other_base == base and level is not None and (best_level is None or level < best_level):
            best, best_level = other, level
    return best


@lru_cache(maxsize=8)
def _generic_tokens(generic_words: tuple[str, ...]) -> frozenset[str]:
    """Accent-free tokens of ``gate.generic_words`` ("cấp lại" → "cap", "lai")."""
    return frozenset(fold_accents(t) for w in generic_words for t in content_tokens(w))


def name_extras(record: ProcedureRecord, question: str, s: RagSettings) -> tuple[int, int]:
    """``(head, total)`` words of the procedure name the question does not ask about.

    Generic words (``gate.generic_words``) and the level tail are ignored; words compare
    accent-free. ``head`` counts the extra words *before* the first asked one: "Trình báo
    mất hộ chiếu" has "trình" before "hộ chiếu", "Cấp hộ chiếu" only the generic "cấp".
    """
    asked = {fold_accents(t) for t in content_tokens(normalize_query(question, s))}
    generic = _generic_tokens(s.gate.generic_words)
    words = [fold_accents(t) for t in content_tokens(twin_key(record)[0])]
    first = next((i for i, w in enumerate(words) if w in asked), len(words))
    extra = [i for i, w in enumerate(words) if w not in asked and w not in generic]
    return sum(1 for i in extra if i < first), len(extra)


def pick_procedure(question: str, result: SearchResult, kb: KnowledgeBase, s: RagSettings) -> str:
    """Procedure of the first hit, unless an equally matching hit names fewer extra things.

    Among retrieved procedures whose :func:`procedure_match_score` ties with the first
    hit's, the one with the fewest extra words at the head of its name wins, then the fewest
    extra words overall, then retrieval order. "Mần cái hộ chiếu mấy ngày thì có?" goes to
    "Cấp hộ chiếu", not "Trình báo mất hộ chiếu"; "Làm lý lịch tư pháp…" to the citizen's
    own request rather than "… theo yêu cầu của cơ quan tiến hành tố tụng" (P8 h-027, h-022).
    """
    pids = list(dict.fromkeys(h.chunk.procedure_id for h in result.hits))
    records = [(i, kb.get_procedure(p)) for i, p in enumerate(pids)]
    top = records[0][1]
    if top is None:
        return pids[0]
    top_match = procedure_match_score(question, top, s)
    tied = [
        (*name_extras(r, question, s), i)
        for i, r in records
        if r is not None and procedure_match_score(question, r, s) == top_match
    ]
    return pids[min(tied)[2]]


def off_topic_phrase(question: str, record: ProcedureRecord, s: RagSettings) -> str | None:
    """A ``gate.out_of_scope_phrases`` topic the question asks about but the procedure lacks.

    "Đi chứng thực bản sao căn cước…" asks about certifying copies, which no police
    procedure does, even if the retrieved "Cấp đổi thẻ căn cước" shares "căn cước" (P8
    h-057). An occurrence right after a document marker ("bản sao có chứng thực", "giấy
    đăng ký kết hôn") names a paper to bring, not the topic, and is ignored.
    """
    normalized = normalize_query(question, s)
    own = fold_accents(f"{record.ten} {record.linh_vuc or ''}".casefold())
    markers = {fold_accents(m) for m in s.gate.document_markers}
    for phrase in s.gate.out_of_scope_phrases:
        if fold_accents(phrase.casefold()) in own:
            continue
        for found in phrase_regex(phrase).finditer(normalized):
            before = _WORD_RE.findall(normalized[: found.start()])[-3:]
            if not markers & {fold_accents(t) for t in before}:
                return phrase
    return None


# ----------------------------------------------------------------------------- citations
def _citations(chunks: Iterable[Chunk], core: str) -> list[Citation]:
    return [chunk.to_citation(citation_quote(chunk.text, core)) for chunk in chunks]


def _best_supporting(sentence: str, chunks: Sequence[Chunk], limit: int) -> list[Chunk]:
    """At most ``limit`` chunks covering most of the sentence's numbers, in original order."""
    if len(chunks) <= limit:
        return list(chunks)
    numbers, words = canonical_numbers(sentence), tokenize(sentence)
    ranked = sorted(
        range(len(chunks)),
        key=lambda i: (
            -len(canonical_numbers(chunks[i].text) & numbers),
            -len(tokenize(chunks[i].text) & words),
            i,
        ),
    )
    return [chunks[i] for i in sorted(ranked[:limit])]


# ----------------------------------------------------------------------------- composer checks
def _form_rejection(text: str) -> str | None:
    """Rejection code for a sentence of the wrong shape (script, length, count), else None."""
    if has_foreign_script(text):
        return "foreign_script"
    if len(text) > MAX_CORE_CHARS:
        return "too_long"
    if count_sentences(text) != 1:
        return "not_one_sentence"
    return None


def _leak_rejection(text: str) -> str | None:
    """``pii_in_answer`` / ``link_in_answer`` for identifying data or a link, else None.

    Also run on template sentences: they copy the record, and a poisoned record must not
    make the engine read out a phone number or a link (red-team IC-P01…P05).
    """
    if redact_pii(text) != text:
        return "pii_in_answer"
    if contains_link(text):
        return "link_in_answer"
    return None


def _content_rejection(text: str) -> str | None:
    """Rejection code for unsafe or identifying content, else None."""
    if refuses_sensitive_request(text) or asks_real_action(text):
        return "unsafe_content"
    if _CLAIMED_ACT_RE.search(text) or _SECRET_HANDOVER_RE.search(text):
        return "unsafe_content"
    return _leak_rejection(text)


def _share(part: set[str], whole: set[str]) -> float:
    return len(part & whole) / len(part) if part else 0.0


def _condition_kept(condition: str, text: str, words: set[str], min_support: float) -> bool:
    """The sentence states the case: its content words, or a case word when it has none."""
    content = tokenize(condition) - _CASE_WORDS
    if not content:
        return CONDITION_WORD_RE.search(text) is not None
    return _share(content, words) >= min_support


def _later_condition(name: str, named: set[str], min_support: float) -> str | None:
    """A case clause anywhere in ``name`` that is about this document itself.

    Real 3.000333 d07 "Văn bản ủy quyền … Trường hợp người được ủy quyền là cha, mẹ … thì
    không cần văn bản ủy quyền": the clause names the document, so it is its case. A clause
    about someone else ("Đối với người chưa đủ 14 tuổi thì người đại diện ký thay") is not.
    """
    for clause in _CASE_CLAUSE_RE.finditer(name):
        if _share(named, tokenize(clause.group(0))) >= min_support:
            return clause.group(0)
    return None


def _case_rejection(text: str, cited: Sequence[Chunk], min_support: float) -> str | None:
    """``unsupported_case`` when a case clause of the sentence matches no case of the source.

    "nếu chưa có thì xuất trình bản chính" can have every word somewhere in the chunk and
    still invert it; each clause must be backed by one source clause on its own.
    """
    sources = [
        tokenize(m.group(0)) - _CASE_WORDS
        for chunk in cited
        for m in _CASE_CLAUSE_RE.finditer(chunk.text)
    ]
    for clause in _CASE_CLAUSE_RE.finditer(text):
        wanted = tokenize(clause.group(0)) - _CASE_WORDS
        if wanted and not any(_share(wanted, src) >= min_support for src in sources):
            return "unsupported_case"
    return None


def _condition_rejection(text: str, record: ProcedureRecord, min_support: float) -> str | None:
    """``drops_condition`` when a document needed only in some case is named without it.

    See :func:`~ctcv_agent.answer_templates.document_condition` for what counts as a case. A
    document is named when most words of its short name — the procedure's own name aside
    ("khai báo tạm vắng" is not "Đề nghị khai báo tạm vắng") — are in the sentence.
    """
    words, own = tokenize(text), tokenize(record.ten)
    common = {d.doc_key for d in common_documents(record)}
    for doc in record.thanh_phan_ho_so:
        name, condition = document_condition(doc)
        named = tokenize(short_doc_name(name, len(name))) - own
        if condition is None:
            condition = _later_condition(name, named, min_support)
        elif doc.doc_key in common:
            continue  # listed under every case: needed whatever the case
        if condition is None or _share(named, words) < min_support:
            continue
        if not _condition_kept(condition, text, words, min_support):
            return "drops_condition"
    return None


def _role_rejection(text: str, cited: Sequence[Chunk], intent: str) -> str | None:
    """``number_wrong_role`` when a deadline answer takes its number from the wrong place.

    For "trong bao lâu phải đi trình báo" (intent ``han_phai_lam``) the processing time of
    ``thoi_han`` ("01 Ngày làm việc") is the right number of the wrong fact (P8 h-008):
    every number must be backed by the cited chunks of the other sections.
    """
    if intent != DEADLINE_INTENT:
        return None
    others = [c.text for c in cited if c.section != _PROCESSING_TIME_SECTION]
    return None if numbers_supported(text, others).ok else "number_wrong_role"


def _validity_rejection(text: str, record: ProcedureRecord) -> str | None:
    """``drops_validity`` when fee amounts are stated without "áp dụng đến hết ngày …"."""
    validity = fee_validity(record)
    if validity is None or not money_amounts(text) or validity[1] in text:
        return None
    return "drops_validity"


def _fee_rejection(text: str, record: ProcedureRecord) -> str | None:
    """Rejection code for a fee statement the record does not back, else None.

    Runs after the number check: numbers already come from the source, this catches
    "free" said of a paid or unknown fee and amounts paired with the wrong channel.
    """
    if claims_free(text) and fee_status(record) != "free":
        return "unsupported_free_claim"
    if fee_channel_mismatch(text, record):
        return "fee_channel_mismatch"
    return None


# ----------------------------------------------------------------------------- trace
def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000.0, 3)


@dataclass
class _Trace:
    """Diagnostics collected while answering (never contains the question)."""

    started: float
    intent: str | None = None
    retrieved: list[str] = field(default_factory=list)
    top_dense: float | None = None
    match: float | None = None
    gate_passed: bool = False
    degraded: bool = False
    composer_sentence: str | None = None
    composer_doc_ids: list[str] = field(default_factory=list)
    composer_error: str | None = None
    fallback_reason: str | None = None
    answer_core: str | None = None
    force_escalate: bool = False
    timings: dict[str, float] = field(
        default_factory=lambda: {"retrieve": 0.0, "compose": 0.0, "verify": 0.0}
    )

    def record_route(self, decision: RouteDecision, result: SearchResult) -> None:
        """Copy the routing outcome."""
        ids = dict.fromkeys(h.chunk.procedure_id for h in result.hits)
        self.retrieved = list(ids)[:MAX_RETRIEVED_IDS]
        self.intent, self.gate_passed, self.degraded = (
            decision.intent,
            decision.passed,
            result.degraded,
        )
        if decision.procedure_id is not None:
            self.top_dense, self.match = decision.dense, decision.match

    def record_composer(self, out: ComposeOutput) -> None:
        """Copy the raw composer reply."""
        self.composer_sentence = out.sentence
        self.composer_doc_ids = list(out.doc_ids)
        self.composer_error = out.error

    def diagnostics(self, hosts: list[str]) -> AskDiagnostics:
        """Freeze into :class:`AskDiagnostics` with the total time."""
        return AskDiagnostics(
            intent=self.intent,
            retrieved_procedure_ids=self.retrieved,
            top_dense=self.top_dense,
            match_score=self.match,
            gate_passed=self.gate_passed,
            answer_core=self.answer_core,
            composer_sentence=self.composer_sentence,
            composer_doc_ids=self.composer_doc_ids,
            composer_error=self.composer_error,
            fallback_reason=self.fallback_reason,
            degraded=self.degraded,
            timings_ms={**self.timings, "total": _ms(self.started)},
            hosts_contacted=hosts,
        )


# ----------------------------------------------------------------------------- engine
class AnswerEngine:
    """Answer service over a knowledge base and an optional composer (see module docstring).

    Args:
        kb: Knowledge base (``FileKnowledgeBase`` in production, ``FakeKnowledgeBase`` in tests).
        composer: Sentence composer, or None to always use templates.
        settings: Resolved ``config/rag.yaml``.
        mode: ``llm_verified`` | ``template_only`` | ``llm_unverified`` (eval only);
            defaults to ``settings.compose_mode``.
        host_sources: Extra objects exposing ``hosts_contacted`` (e.g. the embedder).
        today: Clock for fee validity ("áp dụng đến hết ngày …"); injectable for tests.

    Raises:
        ValueError: for an unknown mode.
    """

    def __init__(
        self,
        kb: KnowledgeBase,
        composer: Composer | None,
        settings: RagSettings,
        mode: str | None = None,
        *,
        host_sources: Sequence[object] = (),
        today: Callable[[], date] = date.today,
    ) -> None:
        """Store the parts; nothing is loaded or called here."""
        chosen = mode or settings.compose_mode
        if chosen not in MODES:
            raise ValueError(f"mode không hợp lệ: {chosen!r} (chỉ {', '.join(MODES)})")
        self.kb, self.composer, self.settings, self.mode = kb, composer, settings, chosen
        self._host_sources = tuple(host_sources)
        self._today = today

    # ------------------------------------------------------------------ routing
    def route(self, question: str) -> RouteDecision:
        """Intent, procedure and gate verdict for ``question`` (used for calibration)."""
        return self._route(redact_pii(question))[0]

    def _route(self, q: str) -> tuple[RouteDecision, SearchResult]:
        s = self.settings
        intent = detect_intent(q, s)
        result = self.kb.search(q, s.retrieval.top_k)
        if not result.hits:
            return RouteDecision(intent, None, 0.0, 0.0, False), result
        pid = pick_procedure(q, result, self.kb, s)
        if not _LEVEL_IN_QUESTION_RE.search(q):
            pid = _local_twin(pid, result, self.kb)
        dense_scores = [
            h.dense_score
            for h in result.hits
            if h.chunk.procedure_id == pid and h.dense_score is not None
        ]
        dense = max(dense_scores, default=0.0)
        record = self.kb.get_procedure(pid)
        match = procedure_match_score(q, record, s) if record is not None else 0.0
        g = s.gate
        passed = (
            record is not None
            and not result.degraded
            and dense >= g.min_dense_score
            and (match >= g.title_overlap_min or dense >= g.high_dense_score)
            and off_topic_phrase(q, record, s) is None
        )
        return RouteDecision(intent, pid, dense, match, passed), result

    def _context(self, pid: str, intent: str, result: SearchResult) -> list[Chunk]:
        """Chunks of the intent's sections (in that order), else the procedure's top hits."""
        s = self.settings
        sections = s.intent_sections.get(intent) or s.intent_sections.get("tong_quan", ())
        chunks = [c for sec in sections for c in self.kb.chunks_for(pid, [sec])]
        if not chunks:
            chunks = [h.chunk for h in result.hits if h.chunk.procedure_id == pid]
        return chunks[: s.retrieval.context_chunks]

    # ------------------------------------------------------------------ answering
    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        """Answer one question (``ctx`` is accepted for the protocol; nothing is stored)."""
        trace = _Trace(started=time.perf_counter())
        if not question or not question.strip():
            return self._no_source(trace, "no_source")
        safety = self._safety(question, trace)
        if safety is not None:
            return safety
        q = redact_pii(question)
        started = time.perf_counter()
        decision, result = self._route(q)
        trace.timings["retrieve"] = _ms(started)
        trace.record_route(decision, result)
        record = self.kb.get_procedure(decision.procedure_id) if decision.passed else None
        if record is None:
            return self._no_source(trace, "no_source")
        context = self._context(record.procedure_id, decision.intent, result)
        return self._answer(q, decision, record, context, trace)

    def _answer(
        self,
        q: str,
        decision: RouteDecision,
        record: ProcedureRecord,
        context: list[Chunk],
        trace: _Trace,
    ) -> AskResult:
        if self.mode == "llm_unverified":
            return self._unverified(q, decision, record, context, trace)
        fee = fee_status(record) if decision.intent == "phi_le_phi" else None
        if fee == "unknown":
            trace.fallback_reason = "fee_unknown"
            return self._no_source(trace, "no_source")
        verified = None
        if fee is not None and fee_expired(record, self._today()):
            trace.fallback_reason = "fee_expired"
        elif fee == "suspicious":
            trace.fallback_reason = "fee_suspicious"
        else:
            verified = self._try_composer(q, decision.intent, context, record, trace)
        mode = "llm_verified"
        if verified is None:
            mode = "template"
            templated = self._template(decision.intent, record, trace)
            if isinstance(templated, str):
                return self._no_source(trace, templated)
            verified = templated
        core, cited = verified
        return self._finish(core, cited, mode, decision, record, trace)

    def _finish(
        self,
        core: str,
        cited: list[Chunk],
        mode: str,
        decision: RouteDecision,
        record: ProcedureRecord,
        trace: _Trace,
    ) -> AskResult:
        answer = f"{core} {closing_for(decision.intent)}"
        citations = _citations(cited, core)
        style = enforce_style(answer, first_turn=False, has_action=False)
        # A sentence that deliberately states no value (suspicious or expired fee) goes to a
        # person.
        trace.force_escalate = mode == "template" and trace.fallback_reason in _NO_VALUE_REASONS
        if not style.ok or requires_citation(answer, citations):
            trace.fallback_reason = trace.fallback_reason or "final_check_failed"
            return self._no_source(trace, "verify_failed")
        trace.answer_core = core
        return self._result(answer, citations, mode, decision, record, trace)

    def _result(
        self,
        answer: str,
        citations: list[Citation],
        mode: str,
        decision: RouteDecision,
        record: ProcedureRecord,
        trace: _Trace,
    ) -> AskResult:
        confidence = self._confidence(decision)
        return AskResult(
            answer=answer,
            citations=citations,
            confidence=confidence,
            escalate=trace.force_escalate or confidence < rules().escalate_confidence,
            refused=False,
            reason="ok",
            answer_mode=mode,
            procedure=ProcedureCard.from_record(record),
            diagnostics=trace.diagnostics(self._hosts()),
        )

    def _confidence(self, decision: RouteDecision) -> float:
        """``w·min(1, dense/high) + (1−w)·match``, clipped to [0, 1]."""
        g = self.settings.gate
        dense_part = min(1.0, decision.dense / g.high_dense_score)
        w = g.confidence_weight_dense
        return round(max(0.0, min(1.0, w * dense_part + (1.0 - w) * decision.match)), 4)

    # ------------------------------------------------------------------ composer
    def _call_composer(self, q: str, context: list[Chunk]) -> ComposeOutput:
        """Call the composer; an exception becomes an error output (never propagates)."""
        started = time.perf_counter()
        try:
            return self.composer.compose(q, context)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — a broken composer must not break answers
            return ComposeOutput(None, (), False, f"unexpected:{type(exc).__name__}", _ms(started))

    def _try_composer(
        self, q: str, intent: str, context: list[Chunk], record: ProcedureRecord, trace: _Trace
    ) -> tuple[str, list[Chunk]] | None:
        """Composer sentence that passed every check, with the chunks it cites; else None."""
        if self.mode == "template_only" or self.composer is None or not context:
            return None
        started = time.perf_counter()
        out = self._call_composer(q, context)
        trace.timings["compose"] = _ms(started)
        trace.record_composer(out)
        if out.error is not None or out.sentence is None:
            trace.fallback_reason = "composer_error" if out.error else "composer_not_sure"
            return None
        started = time.perf_counter()
        checked = self._check_sentence(out.sentence, out.doc_ids, context, record, intent)
        trace.timings["verify"] += _ms(started)
        if isinstance(checked, str):
            trace.fallback_reason = checked
            log.debug("composer sentence rejected", extra={"reason": checked})
            return None
        return checked

    def _check_sentence(
        self,
        sentence: str,
        doc_ids: Sequence[str],
        context: list[Chunk],
        record: ProcedureRecord,
        intent: str = "tong_quan",
    ) -> tuple[str, list[Chunk]] | str:
        """The sentence (banned terms replaced) and its cited chunks, or a rejection code."""
        text = " ".join(sentence.split())
        rejected = _form_rejection(text)
        if rejected is not None:
            return rejected
        text = replace_banned_terms(text)
        rejected = _content_rejection(text)
        if rejected is not None:
            return rejected
        cited = [c for c in context if c.doc_id in set(doc_ids)] or list(context)
        verdict = evaluate_sentence(text, cited, self.settings.gate.lexical_min_support)
        if not verdict.numbers_ok:
            return "unsupported_number"
        floor = self.settings.gate.lexical_min_support
        rejected = (
            _role_rejection(text, cited, intent)
            or _fee_rejection(text, record)
            or _validity_rejection(text, record)
            or _condition_rejection(text, record, floor)
            or _case_rejection(text, cited, floor)
        )
        if rejected is not None:
            return rejected
        # Stricter than evaluate_sentence: every composer sentence must be grounded, a
        # "non-factual" one included (a made-up list of documents has no fee or date in it).
        if verdict.lexical_score < self.settings.gate.lexical_min_support:
            return "low_lexical"
        return (text if text.endswith(_ENDINGS) else f"{text}."), cited

    def _unverified(
        self,
        q: str,
        decision: RouteDecision,
        record: ProcedureRecord,
        context: list[Chunk],
        trace: _Trace,
    ) -> AskResult:
        """Ablation only: the raw composer sentence plus the closing, without any check."""
        started = time.perf_counter()
        out = self._call_composer(q, context) if self.composer is not None else None
        trace.timings["compose"] = _ms(started)
        if out is not None:
            trace.record_composer(out)
        if out is None or out.sentence is None:
            return self._no_source(trace, "no_source")
        core = clip_words(out.sentence, MAX_CORE_CHARS)
        trace.answer_core = core
        answer = f"{core} {closing_for(decision.intent)}"
        citations = _citations(context, core)
        return self._result(answer, citations, "llm_unverified", decision, record, trace)

    # ------------------------------------------------------------------ template
    def _template(
        self, intent: str, record: ProcedureRecord, trace: _Trace
    ) -> tuple[str, list[Chunk]] | Reason:
        """Deterministic sentence with its supporting chunks, or ``no_source``/``verify_failed``."""
        started = time.perf_counter()
        try:
            portal = self.settings.kb.source_portal
            answer = render_template(intent, record, portal, today=self._today())
            if answer is None:
                return "no_source"
            leaked = _leak_rejection(answer.sentence)
            if leaked is not None:
                trace.fallback_reason = leaked
                return "verify_failed"
            pid = record.procedure_id
            chunks = [c for sec in answer.sections for c in self.kb.chunks_for(pid, [sec])]
            limit = self.settings.retrieval.context_chunks
            cited = _best_supporting(answer.sentence, chunks, limit)
            if not cited or not numbers_supported(answer.sentence, [c.text for c in cited]).ok:
                trace.fallback_reason = trace.fallback_reason or "template_unsupported"
                return "verify_failed"
            return answer.sentence, cited
        finally:
            trace.timings["verify"] += _ms(started)

    # ------------------------------------------------------------------ fixed answers
    def _safety(self, question: str, trace: _Trace) -> AskResult | None:
        """Fixed line for sensitive, real-action and pasted-content questions, else None."""
        if refuses_sensitive_request(question):
            return self._fixed(SENSITIVE_LINE, "sensitive", False, trace)
        if asks_real_action(question):
            return self._fixed(REAL_ACTION_LINE, "real_action", False, trace)
        if looks_like_pasted_content(question):
            return self._fixed(PASTED_LINE, "pasted_content", True, trace)
        return None

    def _fixed(self, line: str, reason: Reason, escalate: bool, trace: _Trace) -> AskResult:
        return AskResult(
            answer=line,
            citations=[],
            confidence=1.0,
            escalate=escalate,
            refused=True,
            reason=reason,
            answer_mode="safety",
            procedure=None,
            diagnostics=trace.diagnostics(self._hosts()),
        )

    def _no_source(self, trace: _Trace, reason: Reason) -> AskResult:
        return AskResult(
            answer=NO_SOURCE_LINE,
            citations=[],
            confidence=0.0,
            escalate=True,
            refused=False,
            reason=reason,
            answer_mode="no_source",
            procedure=None,
            diagnostics=trace.diagnostics(self._hosts()),
        )

    def _hosts(self) -> list[str]:
        """Union of ``hosts_contacted`` of the composer, the KB, its embedder and extras."""
        sources: list[Any] = [self.composer, self.kb, *self._host_sources]
        sources.append(getattr(self.kb, "embedder", None))
        hosts: set[str] = set()
        for source in sources:
            hosts.update(getattr(source, "hosts_contacted", None) or ())
        return sorted(hosts)


def build_engine(
    settings: RagSettings | None = None,
    *,
    mode: str | None = None,
    kb: KnowledgeBase | None = None,
    composer: Composer | None = None,
) -> AnswerEngine:
    """Production wiring: file index + Ollama embedder + configured composer.

    The file index and the embedder are imported lazily so that importing this module
    never needs the index. ``mode`` defaults to ``settings.compose_mode``; ``template_only``
    builds no composer.

    Raises:
        KnowledgeBaseNotReady: when the index is missing or stale (API → 503).
    """
    s = settings or load_rag_settings()
    chosen = mode or s.compose_mode
    extra: list[object] = []
    if kb is None:
        from ctcv_agent.rag.embed import OllamaEmbedder
        from ctcv_agent.rag.index import FileKnowledgeBase

        embedder = OllamaEmbedder(s)
        kb = FileKnowledgeBase.load(s, embedder=embedder)
        extra.append(embedder)
    if composer is None and chosen != "template_only":
        composer = build_composer(s)
    return AnswerEngine(kb, composer, s, mode=chosen, host_sources=extra)
