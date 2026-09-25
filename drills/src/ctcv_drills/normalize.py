"""Small text normalisation helpers (diacritics stripping, whole-token matching)."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def strip_diacritics(text: str) -> str:
    """Return ``text`` with Vietnamese diacritics removed (``đ`` → ``d``)."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def ascii_slug(text: str, sep: str = "_") -> str:
    """Lower-case ``text``, drop diacritics and join alphanumeric runs with ``sep``."""
    plain = strip_diacritics(text).lower()
    return _NON_ALNUM_RE.sub(sep, plain).strip(sep)


def contains_token(haystack: str, token: str) -> bool:
    """Return True when ``token`` appears in ``haystack`` delimited by non-alphanumerics."""
    pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def word_count(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())
