"""Deterministic answer sentences and fixed lines of the TTHC answer engine (ADR-007 C4).

``render_template(intent, record, portal)`` builds **one** sentence that starts with
"Theo <portal>, …" and only copies values that are written in the record (amounts from
``phi_vnd`` formatted as ``20.000``, time limits, agency, document and form names, laws,
the first step). Nothing is derived: no count of documents, no sum, no rounding. It returns
None when the record has nothing to say for the intent; the engine then answers "chưa
chắc" and escalates. Every sentence goes through the banned-term replacement and
``enforce_style(first_turn=False, has_action=False)``.

Fees are read against the *wording* of ``phi_le_phi`` (:func:`fee_status`), because the
parsed ``phi_vnd`` can be incomplete (real record 1.001456 kept only the 320.000 re-issue
fee of "160.000/hộ chiếu, … bị mất: 320.000đ") or mistyped (1.001280: "25.000 Đồng
(25.000.000đ/…)"):

* ``stated`` — every channel's amounts are exactly the money written in its text (≤ 3) or
  the text says none → "nộp trực tiếp 20.000 đồng" / "nộp trực tiếp không thu phí";
* ``free`` — **every** channel says none → "không thu phí, lệ phí" (the only case where
  "free" may be said, see :func:`claims_free`);
* ``quoted`` — other wording ("Chưa quy định.", "10 USD", several conditional amounts) →
  the source text is quoted, not paraphrased;
* ``suspicious`` — an amount is 1 000 × another (an extra ".000" group) or ``phi_vnd`` has
  an amount the text does not write → no amount is said and the answer is ``uncertain``
  (the engine escalates and points to the source);
* ``unknown`` — no channel has fee text (P1 flag ``phi_khong_ro``) → None ("chưa chắc").

A fee text may carry its own validity ("… (áp dụng đến hết ngày 31/12/2023 theo Thông tư
…)", real 1.001456): :func:`fee_validity` reads the date. Once it has passed (the engine
passes today's date, injectable for tests) no amount is read out as current: the sentence
says the page gives a rate valid until that day and the engine escalates. While it still
holds, the sentence keeps "áp dụng đến hết ngày …".

A question about the citizen's own deadline ("mất hộ chiếu thì trong bao lâu phải đi trình
báo", intent ``han_phai_lam``) is answered from the conditions or steps, never from the
processing time of ``thoi_han``: :func:`_deadline` quotes the first sentence there that
states a deadline ("Trong thời hạn 02 ngày làm việc kể từ …"), else says nothing.

The fixed lines (safety refusals, "not sure", closings) are the texts of the C4 contract.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from ctcv_agent.guardrails import enforce_style, rules
from ctcv_agent.numeric import canonical_numbers, money_amounts
from ctcv_agent.rag.query import fold_accents
from ctcv_agent.rag.types import CachThuc, DocumentItem, ProcedureRecord
from ctcv_agent.verify import tokenize
from ctcv_core.text import count_sentences

NO_SOURCE_LINE = (
    "Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức. "
    "Bác hỏi cán bộ một cửa hoặc tình nguyện viên giúp cháu nhé."
)
SENSITIVE_LINE = (
    "Bác đừng đọc mã OTP, mật khẩu hay số thẻ cho ai, kể cả người xưng là cán bộ. "
    "Nếu thấy lạ, bác hỏi tình nguyện viên hoặc con cháu trước nhé."
)
REAL_ACTION_LINE = (
    "Cháu không làm thay bác trên ứng dụng hay tài khoản thật được. "
    "Cháu chỉ từng bước để bác tự làm, bác cần hỏi thủ tục nào ạ?"
)
PASTED_LINE = (
    "Nội dung này giống tin nhắn hoặc đường link lạ nên cháu không làm theo. "
    "Bác đừng bấm vào link và hỏi tình nguyện viên giúp nhé."
)
CLOSING_DEFAULT = "Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé."
CLOSING_DOCS = "Bác xem thẻ Giấy tờ cần chuẩn bị ngay bên dưới nhé."
FIXED_LINES: tuple[str, ...] = (
    NO_SOURCE_LINE,
    SENSITIVE_LINE,
    REAL_ACTION_LINE,
    PASTED_LINE,
    CLOSING_DEFAULT,
    CLOSING_DOCS,
)

STEP_MAX_CHARS = 160  # C4: the first step is cut on a word boundary at 160 characters
QUOTE_MAX_CHARS = 300  # C4: a citation quote is at most 2 sentences and 300 characters
QUOTE_MAX_SENTENCES = 2
_NAME_MAX_CHARS = 120
_LAW_MAX_CHARS = 100
_MAX_FEE_CHANNELS = 2  # C4: at most two channels in the fee sentence
_MAX_AMOUNTS = 3
_MAX_TIME_CHANNELS = 3
_NONE_VALUES = frozenset(
    {
        "không",
        "không có",
        "không thu",
        "không thu phí",
        "không thu lệ phí",
        "không thu phí, lệ phí",
        "miễn phí",
        "miễn lệ phí",
        "không quy định",
    }
)
# A fee typed with one extra ".000" group ("25.000 Đồng (25.000.000đ/…)") — a format
# constant of Vietnamese thousands grouping, not a tunable threshold.
_MISTYPE_FACTOR = 1_000
# Accent-free ways of saying "free" (matched on fold_accents(casefold(text))).
_FREE_RE = re.compile(
    r"mien\s+(?:phi|le\s+phi|tien)(?![a-z])"
    r"|khong\s+(?:phai\s+|can\s+|bi\s+)?(?:thu|mat|ton|nop|tra|dong|co|tinh)\s+"
    r"(?:\S+\s+){0,2}?(?:phi|le\s+phi|tien)(?![a-z])"
    r"|(?<![\d.,])0\s*(?:dong|vnd|d)(?![a-z])"
    r"|(?<![a-z])free(?![a-z])"
)
_CHANNEL_WORDS: dict[str, re.Pattern[str]] = {
    "truc_tiep": re.compile(r"(?<![a-z])truc\s+tiep(?![a-z])"),
    "truc_tuyen": re.compile(r"(?<![a-z])(?:truc\s+tuyen|qua\s+mang|tren\s+mang|online)(?![a-z])"),
    "buu_chinh": re.compile(r"(?<![a-z])buu\s+(?:chinh|dien)(?![a-z])"),
}
_CLAUSE_SPLIT_RE = re.compile(r"[,;]|\s(?:còn|con)\s", re.IGNORECASE)
FeeStatus = Literal["stated", "free", "quoted", "suspicious", "unknown"]
_INNER_STOP_RE = re.compile(r"(?<=\S)([.!?…]+)\s+(\S)")
_OPENERS = "\"“‘'([—–-•"
_TRAILING = " .!?;:,-–"
_STEP_PREFIX_RE = re.compile(r"^\s*bước\s*\d+\s*[:.\-–)]?\s*", re.IGNORECASE)
# Parenthesised references to forms or legal texts; other asides ("nếu có") are kept.
_REFERENCE_PAREN_RE = re.compile(
    r"\s*\((?=[^()]*(?:mẫu|ban hành|thông tư|nghị định|quyết định|luật))[^()]*\)",
    re.IGNORECASE,
)
_CLAUSE_END_RE = re.compile(r"(?<=[.!?;])\s+")
# A document needed only in some case: the case column holds the case (or a note), or the
# name carries it inline ("Bản sao giấy khai sinh đối với người chưa đủ 14 tuổi…", "(nếu có)").
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
CONDITION_WORD_RE = re.compile(r"(?<!\w)(?:trường\s+hợp|nếu|đối\s+với)(?!\w)", re.IGNORECASE)
_CONDITION_END_RE = re.compile(r"[;)]|\.(?=\s|$)")
_HEAD_TRAILING = " ,;:(-–"
_ANY_PAREN_RE = re.compile(r"\([^()]*\)")
# "áp dụng đến hết ngày 31/12/2023", "áp dụng tới ngày 1/7/2025" in a fee text.
_VALID_UNTIL_RE = re.compile(
    r"áp\s+dụng\s+(?:đến|tới)\s+(?:hết\s+)?ngày\s+(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})",
    re.IGNORECASE,
)
# A sentence stating the citizen's own deadline: "trong thời hạn 02 ngày", "chậm nhất 30 ngày".
_DEADLINE_RE = re.compile(
    r"(?:trong\s+(?:thời\s+hạn|vòng)|chậm\s+nhất|không\s+quá)\s+(?:là\s+)?\d+\s*"
    r"(?:\([^()]{1,30}\)\s*)?(?:ngày|tháng|năm|giờ)(?!\w)",
    re.IGNORECASE,
)
DEADLINE_INTENT = "han_phai_lam"

Body = tuple[str, tuple[str, ...]]


@dataclass(frozen=True)
class TemplateAnswer:
    """A deterministic answer sentence and the record sections it was copied from.

    ``uncertain`` marks a sentence that deliberately says no value (suspicious fee): the
    engine escalates it.
    """

    sentence: str
    sections: tuple[str, ...]
    uncertain: bool = False


# ----------------------------------------------------------------------------- text helpers
def closing_for(intent: str) -> str:
    """Closing line after the answer: the documents card for document questions."""
    return CLOSING_DOCS if intent == "thanh_phan_ho_so" else CLOSING_DEFAULT


def replace_banned_terms(text: str) -> str:
    """Replace every banned term (``config/guardrails.yaml``) by its plain replacement."""
    terms = sorted(rules().banned_terms, key=lambda b: len(b["term"]), reverse=True)
    for item in terms:
        pattern = re.compile(rf"(?<!\w){re.escape(item['term'])}(?!\w)", re.IGNORECASE)
        text = pattern.sub(item["replacement"], text)
    return text


def _inner_stop(match: re.Match[str]) -> str:
    """``". X"`` → ``"; X"``; a lone ellipsis only changes before a sentence opener."""
    stops, following = match.group(1), match.group(2)
    if set(stops) == {"…"}:
        opener = following.isupper() or following.isdigit() or following in _OPENERS
        return f"{stops}, {following}" if opener else match.group(0)
    return f"; {following}"


def one_sentence(text: str) -> str:
    """Collapse ``text`` into one sentence: inner stops become ``"; "``, one final period."""
    flat = " ".join(text.split()).rstrip(_TRAILING)
    if not flat:
        return ""
    return _INNER_STOP_RE.sub(_inner_stop, flat) + "."


def lower_first(text: str) -> str:
    """Lower-case a capitalised first word (``"Đăng ký"`` → ``"đăng ký"``, ``"CMND"`` kept)."""
    if len(text) >= 2 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


def clip_words(text: str, limit: int) -> str:
    """Cut ``text`` to at most ``limit`` characters on a word boundary, adding ``…``."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    if cut.count("(") > cut.count(")") and cut.rfind("(") > 0:
        cut = cut[: cut.rfind("(")]  # never leave an aside open
    return cut.rstrip(_TRAILING + "(") + "…"


def short_doc_name(text: str, limit: int) -> str:
    """First clause of a document name without form/law asides, cut to ``limit`` characters."""
    flat = " ".join(text.split())
    first = _CLAUSE_END_RE.split(flat, maxsplit=1)[0].rstrip(_TRAILING)
    if first.count("(") > first.count(")") and first.rfind("(") > 0:
        first = first[: first.rfind("(")].rstrip(_TRAILING)  # the clause cut an aside open
    bare = _REFERENCE_PAREN_RE.sub("", first).strip(_TRAILING) or first
    return clip_words(bare, limit)


def document_condition(doc: DocumentItem) -> tuple[str, str | None]:
    """``(document name, case or note it comes with | None)`` of one ``thanh_phan_ho_so`` item.

    ``truong_hop`` is the case ("Trường hợp…") or a note the citizen must hear ("Phiếu được
    tạo lập khi…": the officer prints it) unless it starts with the name (a cut copy, or the
    name followed by a description of the form).
    Otherwise the case is the clause after an inline "đối với / trường hợp / nếu" in the
    name's first sentence (later sentences mostly say who signs; the engine checks those
    that are about the document itself). A name that *starts* with such a word is a case
    statement as a whole.
    """
    name = " ".join(doc.ten_giay_to.split())
    case = " ".join((doc.truong_hop or "").split())
    folded_case, folded_name = case.rstrip("… ").casefold(), name.casefold()
    describes_name = folded_case.startswith(folded_name) or folded_name.startswith(folded_case)
    if case and not describes_name:
        return name, case
    first = _SENTENCE_END_RE.split(name, maxsplit=1)[0]
    found = CONDITION_WORD_RE.search(first)
    if found is None:
        return name, None
    head = name[: found.start()].rstrip(_HEAD_TRAILING)
    if not head:
        return name, name
    tail = first[found.start() :]
    end = _CONDITION_END_RE.search(tail)
    return head, (tail[: end.start()] if end else tail).rstrip(_TRAILING)


def _identity(doc: DocumentItem) -> str:
    """Form code, else the short name without any aside (casefolded)."""
    if doc.mau:
        return doc.mau.casefold()
    name = _ANY_PAREN_RE.sub(" ", short_doc_name(doc.ten_giay_to, len(doc.ten_giay_to)))
    return " ".join(name.casefold().split())


def common_documents(record: ProcedureRecord) -> list[DocumentItem]:
    """Documents needed whatever the case, in record order.

    A document counts when it comes with no case or note (:func:`document_condition`), or
    when the same form or name is listed under *every* case group of ``truong_hop`` (the
    CT01 declaration of "Đăng ký thường trú" appears in each of its groups).
    """
    docs = record.thanh_phan_ho_so
    groups: dict[str, set[str]] = {}
    for doc in docs:
        if doc.truong_hop and document_condition(doc)[1] is not None:
            groups.setdefault(" ".join(doc.truong_hop.split()), set()).add(_identity(doc))
    shared = set.intersection(*groups.values()) if len(groups) > 1 else set()
    return [d for d in docs if document_condition(d)[1] is None or _identity(d) in shared]


def limit_sentences(text: str, limit: int) -> str:
    """Longest word prefix of ``text`` with at most ``limit`` sentences."""
    if count_sentences(text) <= limit:
        return text
    words = text.split(" ")
    for end in range(len(words) - 1, 0, -1):
        candidate = " ".join(words[:end])
        if count_sentences(candidate) <= limit:
            return candidate
    return ""


def citation_quote(text: str, focus: str = "") -> str:
    """Lines of a chunk that best back ``focus`` (numbers first), ≤ 2 sentences, ≤ 300 chars.

    Lines keep their original order; with no ``focus`` the first lines win.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    numbers, words = canonical_numbers(focus), tokenize(focus)

    def weight(i: int) -> tuple[int, int, int]:
        line = lines[i]
        return (len(canonical_numbers(line) & numbers), len(tokenize(line) & words), -i)

    chosen: list[int] = []
    for index in sorted(range(len(lines)), key=weight, reverse=True):
        candidate = sorted([*chosen, index])
        joined = " ".join(lines[j] for j in candidate)
        if len(joined) <= QUOTE_MAX_CHARS and count_sentences(joined) <= QUOTE_MAX_SENTENCES:
            chosen = candidate
    if chosen:
        return " ".join(lines[j] for j in chosen)
    if not lines:
        return ""
    best = lines[max(range(len(lines)), key=weight)]
    return limit_sentences(clip_words(best, QUOTE_MAX_CHARS), QUOTE_MAX_SENTENCES)


def _vnd(amount: int) -> str:
    """``20000`` → ``"20.000"`` (Vietnamese thousands separator)."""
    return f"{amount:,}".replace(",", ".")


def _is_none(text: str | None) -> bool:
    return text is not None and text.casefold().strip(_TRAILING) in _NONE_VALUES


def _ten(record: ProcedureRecord) -> str:
    return lower_first(" ".join(record.ten.split()))


# ----------------------------------------------------------------------------- builders
def _fee_line(channel: CachThuc) -> str | None:
    kenh = channel.kenh_text.casefold()
    if channel.phi_vnd:
        amounts = channel.phi_vnd[:_MAX_AMOUNTS]
        text = " hoặc ".join(f"{_vnd(a)} đồng" for a in amounts)
        suffix = " tùy trường hợp" if len(amounts) > 1 else ""
        return f"nộp {kenh} {text}{suffix}"
    if _is_none(channel.phi_le_phi):
        return f"nộp {kenh} không thu phí"
    return None


def _channel_stated(channel: CachThuc) -> bool:
    """Amounts of the channel are exactly the money its text writes (at most three)."""
    amounts = set(channel.phi_vnd)
    return 0 < len(amounts) <= _MAX_AMOUNTS and money_amounts(channel.phi_le_phi) == amounts


def fee_status(record: ProcedureRecord) -> FeeStatus:
    """How far the fee of ``record`` can be read out (see module docstring)."""
    channels = [c for c in record.cach_thuc if c.phi_le_phi]
    if not channels:
        return "unknown"
    parsed = {a for c in channels for a in c.phi_vnd}
    written = set().union(*(money_amounts(c.phi_le_phi) for c in channels))
    every = parsed | written
    if not parsed <= written or any(a * _MISTYPE_FACTOR in every for a in every if a):
        return "suspicious"
    if all(_is_none(c.phi_le_phi) for c in channels):
        return "free" if len(channels) == len(record.cach_thuc) else "stated"
    if all(_channel_stated(c) or _is_none(c.phi_le_phi) for c in channels):
        return "stated"
    return "quoted"


def claims_free(sentence: str) -> bool:
    """True when ``sentence`` says the procedure costs nothing ("miễn phí", "0 đồng", …)."""
    return _FREE_RE.search(fold_accents(sentence.casefold())) is not None


def fee_channel_mismatch(sentence: str, record: ProcedureRecord) -> bool:
    """True when a clause names one channel with an amount that channel does not charge.

    Catches swapped amounts ("trực tiếp 10.000, trực tuyến 20.000" for 20.000 / 10.000)
    that the number check alone accepts.
    """
    for clause in _CLAUSE_SPLIT_RE.split(sentence):
        folded = fold_accents(clause.casefold())
        kinds = [k for k, pattern in _CHANNEL_WORDS.items() if pattern.search(folded)]
        amounts = money_amounts(clause)
        if len(kinds) != 1 or not amounts:
            continue
        allowed = {
            a
            for c in record.cach_thuc
            if c.kenh == kinds[0]
            for a in (*c.phi_vnd, *money_amounts(c.phi_le_phi))
        }
        if not amounts <= allowed:
            return True
    return False


def fee_validity(record: ProcedureRecord) -> tuple[date, str] | None:
    """Earliest ``(end date, "dd/mm/yyyy" as written)`` of "áp dụng đến hết ngày …" in fees."""
    found: list[tuple[date, str]] = []
    for channel in record.cach_thuc:
        for m in _VALID_UNTIL_RE.finditer(channel.phi_le_phi or ""):
            try:
                end = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
            except ValueError:
                continue  # an impossible date is not a validity clause
            found.append((end, f"{m.group('d')}/{m.group('m')}/{m.group('y')}"))
    return min(found) if found else None


def fee_expired(record: ProcedureRecord, today: date | None) -> bool:
    """True when the fee text says it applied only until a day before ``today``."""
    validity = fee_validity(record)
    return validity is not None and today is not None and validity[0] < today


def _expired_fee(record: ProcedureRecord) -> Body | None:
    validity = fee_validity(record)
    if validity is None:
        return None
    return (
        f"mục phí, lệ phí của thủ tục {_ten(record)} ghi mức thu áp dụng đến hết ngày "
        f"{validity[1]}, nay có thể đã thay đổi nên bác hỏi cán bộ một cửa mức thu hiện hành",
        ("phi_le_phi",),
    )


def _with_validity(body: Body, record: ProcedureRecord) -> Body:
    """Append "áp dụng đến hết ngày …" when the fee text has it (still in force)."""
    validity = fee_validity(record)
    if validity is None or validity[1] in body[0]:
        return body
    return f"{body[0]}, áp dụng đến hết ngày {validity[1]}", body[1]


def _deadline(record: ProcedureRecord) -> Body | None:
    """First sentence of the conditions (else the steps) stating the citizen's deadline."""
    places = [("dieu_kien", record.yeu_cau_dieu_kien or "")]
    places += [("trinh_tu", step) for step in record.trinh_tu]
    for section, text in places:
        for sentence in _SENTENCE_END_RE.split(" ".join(text.split())):
            if _DEADLINE_RE.search(sentence):
                quoted = clip_words(_STEP_PREFIX_RE.sub("", sentence), STEP_MAX_CHARS)
                return f"thủ tục {_ten(record)} ghi: “{quoted}”", (section,)
    return None


def _fee(record: ProcedureRecord) -> Body | None:
    ten, sections, status = _ten(record), ("phi_le_phi",), fee_status(record)
    channels = [c for c in record.cach_thuc if c.phi_le_phi]
    if status == "unknown":
        return None
    if status == "suspicious":
        vague = f"mục phí, lệ phí của thủ tục {ten} ghi chưa rõ ràng"
        return f"{vague} nên cháu chưa đọc chắc được con số", sections
    if status == "free":
        return f"thủ tục {ten} không thu phí, lệ phí", sections
    if status == "stated":
        lines = [line for line in map(_fee_line, channels) if line][:_MAX_FEE_CHANNELS]
        if any(c.phi_vnd for c in channels):
            body = f"phí, lệ phí của thủ tục {ten} là {', '.join(lines)}"
            return _with_validity((body, sections), record)
        return f"thủ tục {ten} {', '.join(lines)}", sections
    text = next(c.phi_le_phi for c in channels if not _is_none(c.phi_le_phi))
    quoted = f"phí, lệ phí của thủ tục {ten} ghi “{clip_words(text, _NAME_MAX_CHARS)}”"
    return _with_validity((quoted, sections), record)


def _time_limit(record: ProcedureRecord) -> Body | None:
    pairs = [
        (c.kenh_text.casefold(), clip_words(c.thoi_han, _NAME_MAX_CHARS))
        for c in record.cach_thuc
        if c.thoi_han
    ][:_MAX_TIME_CHANNELS]
    if not pairs:
        return None
    values = list(dict.fromkeys(v for _, v in pairs))
    said = values[0] if len(values) == 1 else ", ".join(f"nộp {k} {v}" for k, v in pairs)
    return f"thời hạn giải quyết thủ tục {_ten(record)} là {said}", ("thoi_han",)


def _where(record: ProcedureRecord) -> Body | None:
    channels = list(dict.fromkeys(c.kenh_text.casefold() for c in record.cach_thuc))
    how = " hoặc ".join(clip_words(c, 60) for c in channels)
    agency = record.co_quan_thuc_hien
    ten = _ten(record)
    if agency and how:
        return f"thủ tục {ten} do {agency} thực hiện, bác có thể nộp {how}", ("tong_quan",)
    if agency:
        return f"thủ tục {ten} do {agency} thực hiện", ("tong_quan",)
    if how:
        return f"thủ tục {ten} nộp {how}", ("tong_quan",)
    return None


def _documents(record: ProcedureRecord) -> Body | None:
    docs = record.thanh_phan_ho_so
    if not docs:
        return None
    body = f"làm {_ten(record)} cần chuẩn bị các giấy tờ trong danh mục thủ tục"
    common = common_documents(record)
    if not common:  # every document has a case or a note: the card lists them all
        # Worded with the chunk's own words ("Thành phần hồ sơ", "Trường hợp …"): the old
        # "cần chuẩn bị các giấy tờ trong danh mục" had too few of them to pass the
        # citation-support check (dev g-1.003677-giayto, lexical 0.42 < 0.5).
        body = f"hồ sơ thủ tục {_ten(record)} gồm các thành phần tùy từng trường hợp"
        return body, ("thanh_phan_ho_so",)
    name = short_doc_name(common[0].ten_giay_to, _NAME_MAX_CHARS)
    return f"{body}, trong đó có {name}", ("thanh_phan_ho_so",)


def _forms(record: ProcedureRecord) -> Body | None:
    ten = _ten(record)
    if record.bieu_mau:
        name = clip_words(record.bieu_mau[0].ten, _NAME_MAX_CHARS)
        return f"thủ tục {ten} có biểu mẫu {name}", ("bieu_mau",)
    with_form = [d for d in record.thanh_phan_ho_so if d.mau]
    if not with_form:
        return None
    code = Counter(d.mau for d in with_form).most_common(1)[0][0]
    doc = next(d for d in with_form if d.mau == code)
    name = short_doc_name(doc.ten_giay_to, _NAME_MAX_CHARS)
    return f"hồ sơ thủ tục {ten} dùng mẫu {code}, đó là {name}", ("thanh_phan_ho_so",)


def _conditions(record: ProcedureRecord) -> Body | None:
    text = record.yeu_cau_dieu_kien
    if not text:
        return None
    if _is_none(text):
        return f"thủ tục {_ten(record)} không nêu yêu cầu, điều kiện riêng", ("dieu_kien",)
    stated = clip_words(text, STEP_MAX_CHARS)
    return f"điều kiện làm {_ten(record)} là: {stated}", ("dieu_kien",)


def _legal(record: ProcedureRecord) -> Body | None:
    refs = record.can_cu_phap_ly[:2]
    if not refs:
        return None
    names = " và ".join(clip_words(ref.ten, _LAW_MAX_CHARS) for ref in refs)
    return f"căn cứ pháp lý của thủ tục {_ten(record)} có {names}", ("can_cu_phap_ly",)


def _first_step(record: ProcedureRecord) -> Body | None:
    if not record.trinh_tu:
        return None
    step = _STEP_PREFIX_RE.sub("", record.trinh_tu[0])
    step = clip_words(step, STEP_MAX_CHARS)
    if not step:
        return None
    return f"làm {_ten(record)} bước đầu là {step}", ("trinh_tu",)


def _overview(record: ProcedureRecord) -> Body | None:
    return _first_step(record) or _where(record)


_BUILDERS: dict[str, Callable[[ProcedureRecord], Body | None]] = {
    "phi_le_phi": _fee,
    DEADLINE_INTENT: _deadline,
    "thoi_han": _time_limit,
    "thanh_phan_ho_so": _documents,
    "noi_nop": _where,
    "bieu_mau": _forms,
    "dieu_kien": _conditions,
    "can_cu_phap_ly": _legal,
    "trinh_tu": _first_step,
    "tong_quan": _overview,
}


def render_template(
    intent: str, record: ProcedureRecord, portal: str, *, today: date | None = None
) -> TemplateAnswer | None:
    """Deterministic one-sentence answer for ``intent`` (unknown intents use the overview).

    Args:
        intent: Intent key from :func:`ctcv_agent.intents.detect_intent`.
        record: The procedure the gate accepted.
        portal: Publisher named at the start (``config/rag.yaml: kb.source_portal``).
        today: Date the fee validity is compared with (None: validity not checked).

    Returns:
        The sentence and the record sections it copies, or None when the record says
        nothing for this intent or the sentence fails the style check. A fee whose
        validity has passed gives the ``uncertain`` "may have changed" sentence.
    """
    expired = intent == "phi_le_phi" and fee_expired(record, today)
    built = _expired_fee(record) if expired else _BUILDERS.get(intent, _overview)(record)
    if built is None:
        return None
    body, sections = built
    sentence = one_sentence(replace_banned_terms(f"Theo {portal}, {body}"))
    if count_sentences(sentence) != 1:
        return None
    if not enforce_style(sentence, first_turn=False, has_action=False).ok:
        return None
    uncertain = intent == "phi_le_phi" and (expired or fee_status(record) == "suspicious")
    return TemplateAnswer(sentence=sentence, sections=sections, uncertain=uncertain)
