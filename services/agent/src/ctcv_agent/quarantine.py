"""Quarantined reader for untrusted text (CaMeL split, brief D28, SEC-03, ADR-004).

Pasted SMS/Zalo messages, OCR text and web content never reach the planner. They are
summarised here into :class:`QuarantineSummary`, a closed schema with **no free-text
field**: enums, codes, booleans and integers only. Whatever instructions the text
contains ("ignore previous instructions", "send the OTP") are recorded as flags, never
executed. This module must not import the router or the tools (invariant test).

E01 ships :class:`RuleBasedQuarantine` (regexes). E05 may add an LLM-backed summariser
using ``config/prompts/quarantine.v1.md``; it must return the same closed schema.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, Protocol

from pydantic import ConfigDict, Field

from ctcv_agent.guardrails import UNTRUSTED_CLOSE, UNTRUSTED_OPEN
from ctcv_agent.schemas import RedFlag, StrictModel
from ctcv_core.config import load_config

Intent = Literal[
    "yeu_cau_chuyen_tien",
    "doi_otp",
    "doa_dam",
    "link_la",
    "yeu_cau_cai_app",
    "thong_tin_thuong",
    "khac",
]
Impersonates = Literal[
    "cong_an",
    "thue",
    "ngan_hang",
    "shipper",
    "trung_thuong",
    "nguoi_than",
    "dien_luc",
    "buu_dien",
    "khong_ro",
]

MAX_AMOUNT_VND = 10**12


class QuarantineSummary(StrictModel):
    """Closed description of untrusted text. No ``str`` field: nothing here is free text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: Intent
    red_flags: list[RedFlag] = Field(default_factory=list)
    asks_money: bool = False
    asks_otp: bool = False
    amount_vnd: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_VND)
    impersonates: Impersonates = "khong_ro"
    url_count: int = Field(default=0, ge=0)
    has_phone: bool = False
    has_instructions: bool = False


class QuarantineSummarizer(Protocol):
    """Anything that turns untrusted text into a :class:`QuarantineSummary`."""

    def summarize(self, text: str) -> QuarantineSummary:
        """Summarise ``text`` without ever returning its content."""
        ...


# Regexes run on the *folded* text (lower-case, diacritics stripped, đ→d) so that both
# "chuyển tiền" and the SMS spelling "chuyen tien" match; sender tags such as "[NganHang]"
# are written without spaces, hence the optional space in "ngan ?hang".
_OTP_RE = re.compile(
    r"\botp\b|ma xac (?:thuc|nhan)|ma pin\b|mat khau|ma bao mat|\bcvv\b|ma so bi mat"
)
_MONEY_RE = re.compile(
    r"chuyen (?:tien|khoan)|nop (?:tien|phat|phi)|thanh toan|dong phi|nap tien|gui tien"
    r"|\d\s*(?:k|tr|trieu|nghin|ngan)\b|\bvnd\b|\d\s*(?:d|dong)\b"
)
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(trieu|tr|nghin|ngan|k|dong|vnd|d)\b")
_UNIT_MULTIPLIER = {"trieu": 10**6, "tr": 10**6, "nghin": 10**3, "ngan": 10**3, "k": 10**3}
_THREAT_RE = re.compile(
    r"bi khoa|khoa tai khoan|se bi|truy to|bat giam|lenh bat|khoi to|xu ly hinh su|phong toa"
    r"|cat dien|cat dich vu|trong (?:vong )?\d+\s*(?:gio|phut|ngay|tieng)|ngay lap tuc|khan cap"
    r"|ngay hom nay|neu khong"
)
_URL_RE = re.compile(
    r"https?://[^\s]+|www\.[^\s]+"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:xyz|top|club|info|online|site|link|shop|vn|com|net|org|me|io|cc|tk|ml|ga|icu)\b"
)
_APP_RE = re.compile(
    r"cai (?:dat )?(?:app|ung dung|phan mem)|tai (?:app|ung dung|phan mem)|link tai"
)
_PRIZE_RE = re.compile(r"trung thuong|trung giai|qua tang|nhan thuong|nhan qua|tri an|voucher")
_SECRET_RE = re.compile(r"giu bi mat|khong (?:duoc )?(?:noi|ke|tiet lo) (?:voi|cho) ai|\bbi mat\b")
_ACCOUNT_RE = re.compile(
    r"so tai khoan|\bstk\b|tai khoan (?:moi|la|tam|an toan)|chuyen vao tai khoan"
)
_INSTRUCTION_RE = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above|earlier) (?:instructions?|prompts?)"
    r"|bo qua (?:moi |cac |nhung |tat ca )?(?:huong dan|chi dan|lenh|yeu cau)"
    r"|system prompt|you are (?:now )?(?:a|an|the) |ban la (?:tro ly|he thong)"
    r"|act as |developer mode"
    r"|jailbreak|(?:send|read|reveal|doc|gui|forward) (?:the |me |cho toi )?(?:ma )?otp"
)
_IMPERSONATION: tuple[tuple[Impersonates, re.Pattern[str]], ...] = (
    ("cong_an", re.compile(r"cong an|canh sat|bo cong an|vien kiem sat|toa an|dieu tra")),
    ("thue", re.compile(r"cuc thue|chi cuc thue|co quan thue|\bthue\b")),
    ("dien_luc", re.compile(r"dien luc|\bevn\b|tien dien|hoa don dien|cat dien")),
    ("buu_dien", re.compile(r"buu dien|buu cuc|vnpost|buu pham")),
    ("shipper", re.compile(r"shipper|giao hang|don hang|buu kien|van chuyen")),
    ("ngan_hang", re.compile(r"ngan ?hang|\bbank\b|the tin dung|tai khoan ngan ?hang|the atm")),
    ("trung_thuong", re.compile(r"trung thuong|trung giai|nhan thuong")),
    (
        "nguoi_than",
        re.compile(r"\b(?:me|bo|con|chau|anh|chi|em|ong|ba)\s+(?:oi|day)\b|nguoi than|ban than"),
    ),
)
_AGENCY_LIKE: frozenset[str] = frozenset({"cong_an", "thue", "ngan_hang", "dien_luc", "buu_dien"})


def fold(text: str) -> str:
    """Lower-case ``text`` and strip Vietnamese diacritics (đ → d) for accent-free matching."""
    stripped = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", stripped)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").casefold()


def _amount_vnd(folded: str) -> int | None:
    match = _AMOUNT_RE.search(folded)
    if match is None:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None
    value = int(digits) * _UNIT_MULTIPLIER.get(match.group(2), 1)
    return value if 0 < value <= MAX_AMOUNT_VND else None


def _impersonates(folded: str) -> Impersonates:
    for label, pattern in _IMPERSONATION:
        if pattern.search(folded):
            return label
    return "khong_ro"


def _red_flags(
    folded: str, *, asks_otp: bool, asks_money: bool, urls: int, who: str
) -> list[RedFlag]:
    threat = bool(_THREAT_RE.search(folded))
    flags: list[RedFlag] = []
    if asks_money and (threat or asks_otp or urls > 0):
        flags.append("giuc-chuyen-tien")
    if asks_otp:
        flags.append("doi-otp")
    if who in _AGENCY_LIKE:
        flags.append("xung-co-quan")
    if urls > 0:
        flags.append("link-la")
    if threat:
        flags.append("doa-dam")
    if _APP_RE.search(folded):
        flags.append("yeu-cau-cai-app")
    if _SECRET_RE.search(folded):
        flags.append("giu-bi-mat")
    if _ACCOUNT_RE.search(folded):
        flags.append("tai-khoan-la")
    return flags


def _intent(folded: str, *, asks_otp: bool, asks_money: bool, urls: int) -> Intent:
    if asks_otp:
        return "doi_otp"
    if asks_money:
        return "yeu_cau_chuyen_tien"
    if _THREAT_RE.search(folded):
        return "doa_dam"
    if urls > 0:
        return "link_la"
    if _APP_RE.search(folded):
        return "yeu_cau_cai_app"
    if _PRIZE_RE.search(folded):
        return "thong_tin_thuong"
    return "khac"


class RuleBasedQuarantine:
    """Regex summariser: deterministic, model-free, safe for CI (brief D13)."""

    def __init__(self) -> None:
        """Compile the phone regex declared in ``config/guardrails.yaml``."""
        patterns = load_config("guardrails")["pii_patterns"]
        phone = next((p["regex"] for p in patterns if p["name"] == "phone"), None)
        self._phone_re = re.compile(phone) if phone else None

    def summarize(self, text: str) -> QuarantineSummary:
        """Describe ``text`` as a closed schema; the text itself is never returned."""
        raw = text.replace(UNTRUSTED_OPEN, " ").replace(UNTRUSTED_CLOSE, " ")
        folded = fold(raw)
        asks_otp = bool(_OTP_RE.search(folded))
        asks_money = bool(_MONEY_RE.search(folded))
        urls = len(_URL_RE.findall(folded))
        who = _impersonates(folded)
        return QuarantineSummary(
            intent=_intent(folded, asks_otp=asks_otp, asks_money=asks_money, urls=urls),
            red_flags=_red_flags(
                folded, asks_otp=asks_otp, asks_money=asks_money, urls=urls, who=who
            ),
            asks_money=asks_money,
            asks_otp=asks_otp,
            amount_vnd=_amount_vnd(folded),
            impersonates=who,
            url_count=urls,
            has_phone=bool(self._phone_re and self._phone_re.search(raw)),
            has_instructions=bool(_INSTRUCTION_RE.search(folded)),
        )
