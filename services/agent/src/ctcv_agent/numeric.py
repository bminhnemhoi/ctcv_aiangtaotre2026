"""Canonical numbers of Vietnamese text and the "every number comes from the source" check.

An answer about a procedure is only as good as its numbers (fees, days, copies). This module
reduces each number mention to comparable strings so that ``"20.000 đồng"``, ``"20,000"``
and ``"20 nghìn"`` all meet on ``"20000"``:

* digit tokens (a single digit, or digits with ``.``/``,`` inside) lose their separators and
  leading zeros (``"07"`` → ``"7"``, ``"0"`` stays ``"0"``);
* ``<n> nghìn|ngàn`` also yields ``n × 1 000`` and ``<n> triệu`` yields ``n × 1 000 000``
  (a decimal comma is honoured: ``"1,5 triệu"`` → ``"1500000"``);
* the words một … mười right before ngày/tháng/năm/bản/đồng become digits (``"bảy ngày"``);
* a digit run glued after letters is a code, kept whole and lower-cased (``"CT02"`` →
  ``"ct02"``), so a form number never vouches for a quantity;
* the unit written right after a number (optionally after a scale word or a short aside in
  brackets) is kept as a class: ``vnd`` (đồng, đ, VNĐ), ``usd`` (đô la, USD, $), ``eur``,
  ``day`` (ngày, hôm), ``week``, ``month``, ``year``, ``hour``.

:func:`numbers_supported` compares values **and** units (F-01, red-team 25/9): "160.000 đô
la" is not backed by "160.000/hộ chiếu", "7 tháng" is not backed by "07 Ngày làm việc", and
"7 triệu đồng" needs 7 000 000 in the source — the bare 7 of "07 ngày" no longer vouches for
it. An answer number without a unit keeps the old value-only check; a đồng amount is also
backed by a source amount written without unit (fee texts often write "160.000/hộ chiếu").

Nothing here calls a model; the functions are pure and cheap.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

_TOKEN_RE = re.compile(
    r"(?P<code>(?<!\w)[^\W\d_]+\d\w*)"  # letters then digits: CT02, QH14, d01
    r"|(?P<num>(?<![^\W\d_])\d(?:[\d.,]*\d)?)"  # a number not glued after a letter
)
_SCALE_RE = re.compile(r"\s*(?P<scale>nghìn|ngàn|triệu)(?!\w)", re.IGNORECASE)
_DECIMAL_RE = re.compile(r"^\d+,\d{1,2}$")
_SCALES = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000}
_WORD_VALUES = {
    "một": "1",
    "hai": "2",
    "ba": "3",
    "bốn": "4",
    "năm": "5",
    "sáu": "6",
    "bảy": "7",
    "bẩy": "7",
    "tám": "8",
    "chín": "9",
    "mười": "10",
}
_WORD_RE = re.compile(
    r"(?<!\w)(?P<word>" + "|".join(_WORD_VALUES) + r")\s+(?=(?:ngày|tháng|năm|bản|đồng)(?!\w))",
    re.IGNORECASE,
)
# Unit right after a number (or after its scale word), allowing a short aside in brackets
# ("15 (mười lăm) ngày"). Longest spellings first.
_UNIT_RE = re.compile(
    r"\s*(?:\([^()\d]{1,30}\)\s*)?"
    r"(?P<unit>đô[\s-]+la|đô\s+mỹ|usd|us\$|\$|euro|eur|vnđ|vnd|đồng|đ|đô(?!\s+thị)"
    r"|ngày|hôm|tuần|tháng|năm|giờ)(?![^\W\d_])",
    re.IGNORECASE,
)
_UNIT_CLASSES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?:đô|usd|us\$|\$)", re.IGNORECASE), "usd"),
    (re.compile(r"^eu", re.IGNORECASE), "eur"),
    (re.compile(r"^(?:vn|đồng|đ$)", re.IGNORECASE), "vnd"),
    (re.compile(r"^(?:ngày|hôm)$", re.IGNORECASE), "day"),
    (re.compile(r"^tuần$", re.IGNORECASE), "week"),
    (re.compile(r"^tháng$", re.IGNORECASE), "month"),
    (re.compile(r"^năm$", re.IGNORECASE), "year"),
    (re.compile(r"^giờ$", re.IGNORECASE), "hour"),
)
# A đồng amount in the answer may be backed by a source amount written without a unit.
_UNITLESS_OK = frozenset({"vnd"})


# Money in a fee text: a number with thousands groups ("20.000", "25.000.000") or a bare
# number followed by a đồng unit ("500 đồng", "50đ"). Dates, law numbers ("25/2021") and
# foreign-currency amounts ("10 USD") are not VND amounts.
_MONEY_RE = re.compile(
    r"(?<![\d.,/])(?:(?P<grouped>\d{1,3}(?:[.,]\d{3})+)(?!\d)"
    r"|(?P<bare>\d+)(?=\s*(?:đồng|vnđ|vnd|đ)(?![^\W\d_])))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Mention:
    """One number mention: acceptable canonical forms, forms an answer may claim, unit."""

    forms: frozenset[str]
    claimed: frozenset[str]
    unit: str | None


@dataclass(frozen=True)
class NumberCheck:
    """Outcome of :func:`numbers_supported`: ``unsupported`` is sorted and unique."""

    ok: bool
    unsupported: tuple[str, ...] = ()


def _plain(token: str) -> str:
    """Drop separators and leading zeros (``"07"`` → ``"7"``, ``"0"`` → ``"0"``)."""
    digits = token.replace(".", "").replace(",", "")
    return digits.lstrip("0") or "0"


def _scaled(token: str, scale: str) -> str:
    """Value of ``<token> <scale>`` as a plain integer string."""
    factor = _SCALES[scale.casefold()]
    if _DECIMAL_RE.match(token):
        whole, frac = token.split(",")
        value = int(whole) * factor + int(frac) * factor // 10 ** len(frac)
        return str(value)
    return str(int(_plain(token)) * factor)


def _unit_at(text: str, pos: int) -> str | None:
    """Unit class of the unit word starting at ``pos`` (after optional spaces), else None."""
    found = _UNIT_RE.match(text, pos)
    if found is None:
        return None
    word = " ".join(found.group("unit").casefold().split())
    return next((cls for pattern, cls in _UNIT_CLASSES if pattern.search(word)), None)


def _number_mention(text: str, match: re.Match[str]) -> _Mention:
    """Mention of a digit token: plain and scaled forms, the unit written after it."""
    token = match.group("num")
    plain = _plain(token)
    scale = _SCALE_RE.match(text, match.end())
    if scale is None:
        return _Mention(frozenset({plain}), frozenset({plain}), _unit_at(text, match.end()))
    scaled = _scaled(token, scale.group("scale"))
    unit = _unit_at(text, scale.end())
    return _Mention(frozenset({plain, scaled}), frozenset({scaled}), unit)


def _mentions(text: str) -> list[_Mention]:
    """Every number mention of ``text`` with its forms and unit."""
    normalized = unicodedata.normalize("NFC", text or "")
    mentions: list[_Mention] = []
    for match in _TOKEN_RE.finditer(normalized):
        if match.group("code"):
            code = frozenset({match.group("code").casefold()})
            mentions.append(_Mention(code, code, None))
            continue
        mentions.append(_number_mention(normalized, match))
    for match in _WORD_RE.finditer(normalized):
        value = frozenset({_WORD_VALUES[match.group("word").casefold()]})
        mentions.append(_Mention(value, value, _unit_at(normalized, match.end())))
    return mentions


def canonical_numbers(text: str) -> set[str]:
    """Return every canonical number (and letter-digit code) mentioned in ``text``."""
    found: set[str] = set()
    for mention in _mentions(text):
        found |= mention.forms
    return found


def _source_units(sources: Iterable[str]) -> dict[str, set[str | None]]:
    """``{canonical value: units written with it}`` over every source."""
    units: dict[str, set[str | None]] = {}
    for source in sources:
        for mention in _mentions(source):
            for form in mention.forms:
                units.setdefault(form, set()).add(mention.unit)
    return units


def _backed(mention: _Mention, known: dict[str, set[str | None]]) -> bool:
    """A claimed form is in the sources with a compatible unit (see module docstring)."""
    for form in mention.claimed:
        units = known.get(form)
        if units is None:
            continue
        if mention.unit is None or mention.unit in units:
            return True
        if mention.unit in _UNITLESS_OK and None in units:
            return True
    return False


def numbers_supported(answer: str, sources: Iterable[str]) -> NumberCheck:
    """Check that every number mention of ``answer`` appears in at least one source.

    A mention is supported when one of the forms it claims (``"20000"`` for ``"20
    nghìn"``, ``"20"`` for ``"20"``) is among the canonical numbers of the sources, with
    the same unit class when the answer writes one (a đồng amount may also match a source
    amount written without unit).
    """
    known = _source_units(sources)
    missing = {max(m.claimed, key=len) for m in _mentions(answer) if not _backed(m, known)}
    return NumberCheck(ok=not missing, unsupported=tuple(sorted(missing)))


def money_amounts(text: str | None) -> set[int]:
    """VND amounts written as money in ``text`` (``"20.000 đồng/lần"`` → ``{20000}``).

    Used to check a fee sentence against the wording of ``phi_le_phi`` rather than only the
    parsed ``phi_vnd`` list (which can miss "160.000/hộ chiếu" or keep a typo).
    """
    normalized = unicodedata.normalize("NFC", text or "")
    amounts: set[int] = set()
    for match in _MONEY_RE.finditer(normalized):
        token = match.group("grouped") or match.group("bare")
        amounts.add(int(token.replace(".", "").replace(",", "")))
    return amounts
