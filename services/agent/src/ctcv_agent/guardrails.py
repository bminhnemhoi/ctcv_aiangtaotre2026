"""Hard guardrails of the coach, driven by ``config/guardrails.yaml`` (brief §7, §8).

Nothing here calls a model. The functions are pure and cheap so they run on every
input (before the planner) and every output (before TTS), and so the red-team runner
(``make redteam``) can exercise them without a GPU.

v2 (red-team F-04/F-05, P8 h-077, 25/9) — without touching the E01 regexes of
``config/guardrails.yaml``:

* a text typed without diacritics ("gui mat khau VNeID", "nop giup bac ho so") is also
  matched against accent-free copies of the sensitive/real-action patterns; alternatives
  that are ambiguous once unaccented ("ho" = hộ/hồ/họ, "noi" = nói/nơi, "go", "thay" =
  thay/thấy/thầy) are left out of the copies;
* asking for a code without naming it ("đọc cái mã 6 số vừa về máy") is a sensitive request;
* delegation with a long object ("gửi đơn … lên cổng dịch vụ công giùm bác") is a real
  action unless the favour is guidance ("chỉ giùm", "nói giúp"); "hộ" of a procedure noun
  ("làm hộ chiếu") is not "on behalf of";
* identifiers written in digit groups ("001 234 567 890", "0912.345.678") are joined before
  the configured PII patterns run, so they are redacted like the solid forms.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from ctcv_agent.schemas import ActionHint, Citation, StyleVerdict
from ctcv_core.config import load_config
from ctcv_core.logging import load_pii_patterns, scrub_pii
from ctcv_core.text import contains_banned_terms, count_sentences

UNTRUSTED_OPEN = "<<<UNTRUSTED>>>"
UNTRUSTED_CLOSE = "<<<END>>>"

# "hộ" starts procedure nouns ("hộ chiếu", "hộ khẩu", "hộ tịch", "hộ gia đình") and also
# means "on behalf of" ("làm hộ tôi"); the noun's "hộ" is unaccented before matching.
_HO_NOUN_RE = re.compile(
    r"(?<!\w)hộ(?=\s+(?:chiếu|khẩu|tịch|gia\s+đình|kinh\s+doanh)(?!\w))", re.IGNORECASE
)
# "nộp hồ sơ giúp tôi", "gửi đơn … lên cổng dịch vụ công giùm bác": an action verb, at most
# twelve words, then "giúp/giùm/hộ/thay" + person (P8 h-077 had ten words in between).
_DELEGATION_RE = re.compile(
    r"(?<!\w)(?:làm|nộp|điền|khai|gửi|bấm|ký|đăng\s+nhập|đăng\s+ký|thanh\s+toán|chuyển)"
    r"(?P<between>(?:\s+\S+){0,12}?)\s+(?:giúp|giùm|hộ|thay)\s+"
    r"(?:tôi|tui|cháu|bác|cô|chú|ông|bà|mình|em|con|anh|chị)(?!\w)",
    re.IGNORECASE,
)
_FOLDED_DELEGATION_RE = re.compile(
    r"(?<!\w)(?:lam|nop|dien|khai|gui|bam|ky|dang\s+nhap|dang\s+ky|thanh\s+toan|chuyen)"
    r"(?P<between>(?:\s+\S+){0,12}?)\s+(?:giup|gium)\s+"
    r"(?:toi|tui|chau|bac|co|chu|ong|ba|minh|em|con|anh|chi)(?!\w)",
    re.IGNORECASE,
)
# "làm ơn chỉ giùm bác", "… nói giúp bác với": the favour asked is guidance, not an act.
_GUIDANCE_RE = re.compile(
    r"(?<!\w)(?:chỉ|chi|hướng\s+dẫn|huong\s+dan|nói|giải\s+thích|giai\s+thich|xem|tra|hỏi"
    r"|hoi|kiểm\s+tra|kiem\s+tra|tìm|tim|đọc|cho\s+biết|cho\s+biet)(?!\w)",
    re.IGNORECASE,
)
# Asking for a code without naming it: "đọc cái mã 6 số vừa về máy", "gửi mã vừa nhận".
_UNNAMED_CODE_RE = re.compile(
    r"(?i)(?<!\w)(?:đọc|doc|gửi|gui|nói|cho|báo|bao|nhắn|nhan|cung\s+cấp|cung\s+cap)\s+"
    r"(?:\S+\s+){0,4}?(?:mã|ma)\s+(?:\d+\s+(?:số|so|chữ\s+số|chu\s+so)|(?:số\s+|so\s+)?"
    r"(?:vừa|vua)\s+(?:nhận|nhan|về|ve|gửi|gui|nhắn|nhan)|(?:gửi|gui)\s+(?:về|ve)"
    r"|(?:nhận|nhan)\s+(?:được|duoc))"
)
# Alternatives that become ambiguous once unaccented; left out of the accent-free copies.
_AMBIGUOUS_UNACCENTED = ("ho", "noi", "go", "thay")
# Accented letters a text may carry and still count as typed without diacritics.
_MAX_ACCENTED_IN_PLAIN = 2
# Digit groups of an identifier: "001 234 567 890", "0912.345.678", "0912-345-678".
_DIGIT_GROUPS_RE = re.compile(r"(?<![\d.,])(?:\+84|\d{2,4})(?:[ .-]\d{2,4}){2,4}(?![\d])")

# Structural words that introduce a button label in a coach line ("nút xanh có chữ Quét QR").
LABEL_MARKERS: tuple[str, ...] = ("chữ", "ghi", "tên")
_QUOTE_RE = re.compile(r"[\"“”‘’«»][^\"“”‘’«»]{1,60}[\"“”‘’«»]")
_NUMBER_RE = re.compile(r"\d[\d.,]*")

# Signals that a message is third-party content (SMS/Zalo/web) rather than the learner's
# own words. Such content is routed to the quarantine, never to the planner (SEC-03).
_PASTED_URL_RE = re.compile(
    r"(?i)(?:https?://|www\.)\S+|\b[\w-]+\.(?:xyz|top|club|info|online|site|link|shop|icu|tk|ml|ga|cc)\b"
)
_PASTED_TAG_RE = re.compile(r"^\s*\[[^\]\n]{1,40}\]")
# "Tin nhắn:", "Tin nhắn của cán bộ:", "Zalo từ số lạ -" (up to four words before the colon).
_PASTED_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:tin nhắn|tin nhan|sms|zalo|nội dung|noi dung|email|thư)(?:\s+[^\s:]+){0,4}?"
    r"\s*[:\-]"
)
# An instruction to open a link, even without a URL ("bấm vào đường link để nhận hỗ trợ").
_LINK_CUE_RE = re.compile(
    r"(?i)(?:bấm|bam|nhấn|nhan|kích|kich|click|truy\s+cập|truy\s+cap|mở|mo)\s+(?:vào\s+|vao\s+)?"
    r"(?:cái\s+|cai\s+)?(?:đường\s+|duong\s+)?(?:link|liên\s+kết|lien\s+ket)(?!\w)"
)
# A phone number alone is not proof of pasted content ("con bác số 09… bảo chuyển tiền" is
# the learner speaking and is simply redacted); a phone number next to a call-to-action cue is.
_SMS_CUE_RE = re.compile(
    r"(?i)gọi ngay|goi ngay|liên hệ|lien he|trúng thưởng|trung thuong|nhận thưởng|nhan thuong"
    r"|nhận quà|nhan qua|truy cập|truy cap|bấm vào|bam vao|kích vào|kich vao|hotline"
)
_INJECTION_RE = re.compile(
    r"(?i)ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?)"
    r"|(?:bỏ|bo)\s+qua\s+(?:mọi\s+|moi\s+|các\s+|cac\s+|những\s+|nhung\s+|tất\s+cả\s+|tat\s+ca\s+)?"
    r"(?:hướng\s+dẫn|huong\s+dan|chỉ\s+dẫn|chi\s+dan|lệnh|lenh|yêu\s+cầu|yeu\s+cau)"
    r"|system\s+prompt|you\s+are\s+(?:now\s+)?(?:a|an|the)\s|(?:bạn|ban)\s+(?:là|la)\s+(?:trợ\s+lý|tro\s+ly|hệ\s+thống|he\s+thong)"
    r"|act\s+as\s|developer\s+mode|jailbreak"
)


@dataclass(frozen=True)
class GuardrailRules:
    """Compiled view of ``config/guardrails.yaml``."""

    max_sentences: int
    escalate_confidence: float
    pii: tuple[tuple[re.Pattern[str], str], ...]
    sensitive_request: tuple[re.Pattern[str], ...]
    real_action: tuple[re.Pattern[str], ...]
    banned_terms: tuple[Mapping[str, str], ...]
    action_verb_re: re.Pattern[str]
    color_re: re.Pattern[str]
    intent_markers: tuple[str, ...]
    fact_indicators: tuple[re.Pattern[str], ...]
    phone_re: re.Pattern[str] | None
    sensitive_plain: tuple[re.Pattern[str], ...] = ()
    real_action_plain: tuple[re.Pattern[str], ...] = ()


def _word_alternation(words: Iterable[str]) -> re.Pattern[str]:
    ordered = sorted({w for w in words if w}, key=len, reverse=True)
    body = "|".join(re.escape(w) for w in ordered)
    return re.compile(rf"(?<!\w)(?:{body})(?!\w)", re.IGNORECASE)


def _compile_all(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


def fold_vietnamese(text: str) -> str:
    """Remove Vietnamese diacritics (NFD, drop marks, đ → d); length-preserving on NFC text."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped.replace("đ", "d").replace("Đ", "D"))


def _without_ambiguous(source: str) -> str:
    """Drop ambiguous unaccented words from the alternations of a regex source."""
    for word in _AMBIGUOUS_UNACCENTED:
        source = re.sub(rf"(?<=[(|:]){word}\|", "", source)
        source = re.sub(rf"\|{word}(?=[|)])", "", source)
    return source


def _compile_plain(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    """Accent-free copies of ``patterns`` for texts typed without diacritics."""
    return tuple(re.compile(_without_ambiguous(fold_vietnamese(p))) for p in patterns)


def _typed_without_diacritics(text: str) -> bool:
    folded = fold_vietnamese(text)
    changed = sum(1 for a, b in zip(text, folded, strict=False) if a != b)
    return changed <= _MAX_ACCENTED_IN_PLAIN


@lru_cache(maxsize=1)
def rules() -> GuardrailRules:
    """Load and compile the guardrail config once (call :func:`clear_rules_cache` to reload)."""
    cfg = load_config("guardrails")
    phone = next((p["regex"] for p in cfg["pii_patterns"] if p["name"] == "phone"), None)
    return GuardrailRules(
        max_sentences=int(cfg["max_sentences"]),
        escalate_confidence=float(cfg["escalate_confidence"]),
        pii=tuple(load_pii_patterns(cfg)),
        sensitive_request=_compile_all(cfg["sensitive_request_patterns"]),
        real_action=_compile_all(cfg["real_action_patterns"]),
        banned_terms=tuple(cfg["banned_terms"]),
        action_verb_re=_word_alternation(cfg["action_verbs"]),
        color_re=_word_alternation(cfg["colors"]),
        intent_markers=tuple(str(m) for m in cfg["intent_confirmation_markers"]),
        fact_indicators=_compile_all(cfg["fact_indicator_patterns"]),
        phone_re=re.compile(phone) if phone else None,
        sensitive_plain=_compile_plain(cfg["sensitive_request_patterns"]),
        real_action_plain=_compile_plain(cfg["real_action_patterns"]),
    )


def clear_rules_cache() -> None:
    """Drop the compiled rules (tests that change the config call this)."""
    rules.cache_clear()


# ----------------------------------------------------------------------------- input side
def _join_digit_groups(text: str, r: GuardrailRules) -> str:
    """Join "001 234 567 890"-style groups when the joined digits are PII (else keep them)."""

    def join(match: re.Match[str]) -> str:
        joined = re.sub(r"[ .-]", "", match.group(0))
        return joined if scrub_pii(joined, r.pii) != joined else match.group(0)

    return _DIGIT_GROUPS_RE.sub(join, text)


def redact_pii(text: str) -> str:
    """Replace CCCD, card, OTP, phone and e-mail patterns with the redaction token.

    Digit groups separated by spaces, dots or dashes are joined first when the joined number
    is itself PII, so "0912.345.678" is redacted like "0912345678" (red-team F-05).
    """
    r = rules()
    return scrub_pii(_join_digit_groups(text, r), r.pii)


def refuses_sensitive_request(text: str) -> bool:
    """True when ``text`` asks the learner (or the coach) to reveal OTP/password/card/CCCD."""
    r = rules()
    if any(p.search(text) for p in r.sensitive_request) or _UNNAMED_CODE_RE.search(text):
        return True
    if _typed_without_diacritics(text):
        folded = fold_vietnamese(text)
        return any(p.search(folded) for p in r.sensitive_plain)
    return False


def _delegates(text: str, pattern: re.Pattern[str]) -> bool:
    return any(not _GUIDANCE_RE.search(m.group("between")) for m in pattern.finditer(text))


def refuses_real_action(text: str) -> bool:
    """True when ``text`` asks the coach to act on a real app/account on the user's behalf.

    "Làm hộ chiếu mất bao nhiêu tiền?" is a question; "nộp hồ sơ giúp tôi", "gửi đơn … lên
    cổng giùm bác" and "nop giup bac ho so" ask the assistant to act for the citizen.
    """
    r = rules()
    masked = _HO_NOUN_RE.sub("ho", text)
    if any(p.search(masked) for p in r.real_action) or _delegates(masked, _DELEGATION_RE):
        return True
    if _typed_without_diacritics(text):
        folded = fold_vietnamese(text)
        if any(p.search(folded) for p in r.real_action_plain):
            return True
        return _delegates(folded, _FOLDED_DELEGATION_RE)
    return False


def looks_like_pasted_content(text: str) -> bool:
    """Heuristic: does ``text`` look like pasted third-party content (SMS, link, injection)?

    The API layer should pass pasted content explicitly; this is the safety net when a
    citizen types or dictates a message into the question box.
    """
    if not text or not text.strip():
        return False
    if _PASTED_URL_RE.search(text) or _PASTED_TAG_RE.search(text) or _PASTED_PREFIX_RE.search(text):
        return True
    if _LINK_CUE_RE.search(text):
        return True
    if _INJECTION_RE.search(text):
        return True
    if len([line for line in text.splitlines() if line.strip()]) >= 2:
        return True
    phone = rules().phone_re
    return bool(phone and phone.search(text) and _SMS_CUE_RE.search(text))


def contains_link(text: str) -> bool:
    """True when ``text`` holds a URL or a bare domain of a link-shortener style TLD."""
    return bool(text) and _PASTED_URL_RE.search(text) is not None


def treat_pasted_as_data(text: str) -> str:
    """Wrap untrusted text in the quarantine markers so a reader model sees it as data only.

    Any marker already inside the text is removed first, so pasted content cannot close
    the data block early. The wrapped string is meant for the quarantine prompt
    (``config/prompts/quarantine.v1.md``) and must never reach the planner.
    """
    body = text.replace(UNTRUSTED_OPEN, "").replace(UNTRUSTED_CLOSE, "").strip()
    return f"{UNTRUSTED_OPEN}\n{body}\n{UNTRUSTED_CLOSE}"


# ----------------------------------------------------------------------------- output side
def _has_intent_confirmation(say: str, r: GuardrailRules) -> bool:
    lowered = say.casefold()
    return any(marker.casefold() in lowered for marker in r.intent_markers)


def _has_label(tail: str) -> bool:
    """True when the text after a colour word names a button label."""
    for marker in LABEL_MARKERS:
        if re.search(rf"(?<!\w){re.escape(marker)}\s+\S", tail):
            return True
    if _QUOTE_RE.search(tail):
        return True
    return any(token[:1].isupper() for token in tail.split())


def _action_reasons(say: str, r: GuardrailRules, hint: ActionHint | None) -> list[str]:
    reasons: list[str] = []
    if not r.action_verb_re.search(say):
        reasons.append("thiếu động từ hành động cụ thể (bấm/chọn/nhập…)")
    color = r.color_re.search(say)
    if color is None:
        reasons.append("thiếu màu của nút hoặc ô cần chạm")
    elif not _has_label(say[color.end() :]):
        reasons.append("thiếu chữ trên nút sau màu")
    if hint is not None:
        lowered = say.casefold()
        if hint.color.casefold() not in lowered:
            reasons.append(f"câu nói không nêu màu '{hint.color}' của action_hint")
        if hint.label.casefold() not in lowered:
            reasons.append(f"câu nói không nêu chữ '{hint.label}' của action_hint")
    return reasons


def enforce_style(
    say: str,
    first_turn: bool,
    has_action: bool = True,
    hint: ActionHint | None = None,
) -> StyleVerdict:
    """Check a coach line against the speaking rules (idea §5 pedagogy 1–2, brief §7).

    Args:
        say: The line the coach is about to say.
        first_turn: When True the line must contain a question confirming the intent.
        has_action: When True the line must name a concrete action with a colour and a
            button label; pass False for pure intent-confirmation or escalation lines.
        hint: Optional action hint the line must mention (colour + label).
    """
    r = rules()
    reasons: list[str] = []
    sentences = count_sentences(say)
    if sentences == 0:
        reasons.append("câu nói rỗng")
    elif sentences > r.max_sentences:
        reasons.append(f"quá {r.max_sentences} câu ({sentences} câu)")
    if first_turn and not _has_intent_confirmation(say, r):
        reasons.append("lượt đầu phải có câu hỏi xác nhận ý định")
    if has_action and sentences > 0:
        reasons.extend(_action_reasons(say, r, hint))
    banned = contains_banned_terms(say, r.banned_terms)
    if banned:
        replacements = {b["term"]: b["replacement"] for b in r.banned_terms}
        reasons.append(
            "thuật ngữ cấm: " + ", ".join(f"{t} → {replacements.get(t, '?')}" for t in banned)
        )
    return StyleVerdict(ok=not reasons, reasons=reasons, sentences=sentences)


def _mask_known_numbers(answer: str, known_values: Iterable[Any]) -> str:
    known = {re.sub(r"\D", "", str(v)) for v in known_values}
    known.discard("")
    if not known:
        return answer
    return _NUMBER_RE.sub(
        lambda m: "" if re.sub(r"\D", "", m.group(0)) in known else m.group(0), answer
    )


def has_factual_claim(answer: str, *, known_values: Iterable[Any] = ()) -> bool:
    """True when ``answer`` states something that needs a source (dates, fees, rules, laws).

    Numbers that already appear in ``known_values`` (the sandbox state) do not count:
    "Bác gõ 200.000 đồng" repeats the scenario goal rather than asserting a fact.
    """
    masked = _mask_known_numbers(answer, known_values)
    return any(p.search(masked) for p in rules().fact_indicators)


def _count_valid_citations(citations: Sequence[Citation | Mapping[str, Any]] | None) -> int:
    count = 0
    for item in citations or ():
        if isinstance(item, Citation):
            count += 1
            continue
        try:
            Citation.model_validate(item)
        except ValidationError:
            continue
        count += 1
    return count


def requires_citation(
    answer: str,
    citations: Sequence[Citation | Mapping[str, Any]] | None = (),
    *,
    known_values: Iterable[Any] = (),
) -> bool:
    """Return True when ``answer`` states a fact that no valid citation backs.

    True means the answer must not be read out as is: the coach replaces it with the
    "chưa chắc" line and escalates. False means either no factual claim was found or
    at least one valid :class:`Citation` accompanies it.
    """
    if not has_factual_claim(answer, known_values=known_values):
        return False
    return _count_valid_citations(citations) == 0
