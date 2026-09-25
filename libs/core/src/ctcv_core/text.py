"""Vietnamese text helpers used by guardrails, validators and evaluation.

The sentence counter is deliberately conservative: a period, question or
exclamation mark (or an ellipsis) ends a sentence only when it is followed by
the end of the text or by whitespace and an upper-case letter, a digit or an
opening quote/bracket. Decimal/thousand separators (``200.000đ``) and common
abbreviations (``TP.``, ``TS.``) never end a sentence.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

DEFAULT_ABBREVIATIONS: tuple[str, ...] = (
    "TP",
    "Tp",
    "TT",
    "TS",
    "ThS",
    "GS",
    "PGS",
    "BS",
    "KS",
    "Q",
    "P",
    "H",
    "X",
    "KP",
    "VD",
    "Tr",
    "Mr",
    "Mrs",
    "Ms",
    "Dr",
    "St",
    "No",
)

# Sentinel that replaces dots which must not terminate a sentence (U+FFFC).
_PROTECT = "￼"
_ELLIPSIS = "…"
_ELLIPSIS_RE = re.compile(r"(?:\.\s?){3,}|…+")
_NUMBER_SEPARATOR_RE = re.compile(r"(?<=\d)[.,](?=\d)")
# Chained initials such as "T.P." or "U.S." — a lone "A." is left alone because it is
# just as likely to end a sentence ("... Nguyễn Văn A. Anh ấy ...").
_INITIALS_RE = re.compile(r"(?<![\w￼])(?:[A-ZĐ]\.){2,}")
_TERMINATOR_RE = re.compile(r"[.!?…]+[\"”’')\]]*")
_OPENERS = "\"“‘'([—–-•"


def _abbreviation_re(extra: Iterable[str]) -> re.Pattern[str]:
    words = sorted({*DEFAULT_ABBREVIATIONS, *extra}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + r")\.")


def _protect(text: str, extra_abbreviations: Iterable[str]) -> str:
    """Neutralise dots that are not sentence terminators."""
    text = _ELLIPSIS_RE.sub(_ELLIPSIS, text)
    text = _NUMBER_SEPARATOR_RE.sub(_PROTECT, text)
    text = _abbreviation_re(extra_abbreviations).sub(lambda m: m.group(1) + _PROTECT, text)
    return _INITIALS_RE.sub(lambda m: m.group(0).replace(".", _PROTECT), text)


def _is_boundary(text: str, pos: int) -> bool:
    rest = text[pos:]
    if not rest.strip():
        return True
    if not rest[0].isspace():
        return False
    nxt = rest.lstrip()[0]
    return nxt.isupper() or nxt.isdigit() or nxt in _OPENERS


def count_sentences(text: str, *, extra_abbreviations: Iterable[str] = ()) -> int:
    """Count sentences in Vietnamese ``text``.

    Returns 0 for empty/blank input and 1 for text without any terminator.
    """
    if not text or not text.strip():
        return 0
    prepared = _protect(text.strip(), extra_abbreviations)
    count = 0
    last_end = 0
    for match in _TERMINATOR_RE.finditer(prepared):
        if not _is_boundary(prepared, match.end()):
            continue
        if prepared[last_end : match.start()].strip():
            count += 1
        last_end = match.end()
    if prepared[last_end:].strip():
        count += 1
    return count


def _term_of(item: str | Mapping[str, str]) -> str:
    return str(item["term"]) if isinstance(item, Mapping) else str(item)


def contains_banned_terms(text: str, banned: Iterable[str | Mapping[str, str]]) -> list[str]:
    """Return banned terms present in ``text`` as whole words, ordered by first occurrence.

    ``banned`` accepts plain strings or mappings with a ``term`` key (the shape
    used by ``config/guardrails.yaml: banned_terms``). Matching is case-insensitive.
    """
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for item in banned:
        term = _term_of(item)
        if not term or term.casefold() in seen:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            seen.add(term.casefold())
            hits.append((match.start(), term))
    return [term for _, term in sorted(hits)]
