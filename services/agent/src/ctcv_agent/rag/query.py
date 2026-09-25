"""Query normalisation for TTHC retrieval (ADR-007 C4).

* :func:`normalize_query` — NFC, casefold, collapse whitespace, then rewrite regional
  phrases (``config/rag.yaml: retrieval.dialect_phrases``) only when the whole phrase
  matches on word boundaries, in a single pass (a rewrite never triggers another);
* :func:`fold_accents` — strip Vietnamese diacritics (``đ`` → ``d``) for accent-free matching;
* :func:`content_tokens` / :func:`syllable_bigrams` — tokens used by lexical scoring;
* :func:`expand_synonyms` — extra phrases from ``retrieval.synonyms`` groups the query hits.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache

from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.verify import STOPWORDS

_TOKEN_RE = re.compile(r"\w+")
_WHITESPACE_RE = re.compile(r"\s+")
# Standard compounds whose first syllable is also a regional question word: "chi phí"
# (cost), "chi tiết" (details)... A dialect phrase ending in the key is never rewritten
# when the next word completes one of these compounds ("cần chi phí" stays as it is).
_PROTECTED_NEXT_WORDS: dict[str, tuple[str, ...]] = {
    "chi": ("phí", "tiết", "trả", "tiêu", "nhánh", "cục", "bộ", "hội", "đoàn", "viện"),
}


def _nfc_fold(text: str) -> str:
    """NFC + casefold + single spaces, stripped."""
    folded = unicodedata.normalize("NFC", text).casefold()
    return _WHITESPACE_RE.sub(" ", folded).strip()


def _phrase_pattern(phrase: str) -> str:
    """Regex for ``phrase`` as whole words, with the compound guard of its last word."""
    last = phrase.rsplit(" ", 1)[-1]
    guard = ""
    if last in _PROTECTED_NEXT_WORDS:
        tails = "|".join(re.escape(w) for w in _PROTECTED_NEXT_WORDS[last])
        guard = rf"(?!\s+(?:{tails})(?!\w))"
    return rf"(?<!\w){re.escape(phrase)}(?!\w){guard}"


@lru_cache(maxsize=16)
def _dialect_rewriter(
    pairs: tuple[tuple[str, str], ...],
) -> tuple[re.Pattern[str] | None, dict[str, str]]:
    """Compile one alternation (longest phrase first) and its replacement table."""
    table: dict[str, str] = {}
    for source, target in pairs:
        table.setdefault(_nfc_fold(source), _nfc_fold(target))
    if not table:
        return None, table
    ordered = sorted(table, key=len, reverse=True)
    pattern = re.compile("|".join(f"(?:{_phrase_pattern(p)})" for p in ordered))
    return pattern, table


def normalize_query(text: str, s: RagSettings | None = None) -> str:
    """Normalise a citizen question for retrieval (see module docstring).

    Args:
        text: Raw (already PII-redacted) question.
        s: Settings; loaded from ``config/rag.yaml`` when omitted.
    """
    settings = s or load_rag_settings()
    normalized = _nfc_fold(text)
    pattern, table = _dialect_rewriter(settings.retrieval.dialect_phrases)
    if pattern is None:
        return normalized
    return pattern.sub(lambda m: table[m.group(0)], normalized)


def fold_accents(text: str) -> str:
    """Remove Vietnamese diacritics: NFD, drop combining marks, ``đ``/``Đ`` → ``d``/``D``."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped.replace("đ", "d").replace("Đ", "D"))


def content_tokens(text: str) -> list[str]:
    """Casefolded word tokens of ``text`` in order, stopwords removed (duplicates kept)."""
    tokens = (m.group(0) for m in _TOKEN_RE.finditer(unicodedata.normalize("NFC", text)))
    return [t for t in (tok.casefold() for tok in tokens) if t not in STOPWORDS]


def syllable_bigrams(tokens: Sequence[str]) -> list[str]:
    """Adjacent token pairs joined by ``_`` (``["đăng", "ký"]`` → ``["đăng_ký"]``)."""
    return [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]


def _contains(text: str, phrase: str) -> bool:
    """True when ``phrase`` occurs in ``text`` as whole words."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def expand_synonyms(text: str, s: RagSettings | None = None) -> list[str]:
    """Return the other members of every synonym group the query mentions.

    A group is hit when one member occurs as whole words in the normalised query, or (with
    ``retrieval.accent_fold``) in its accent-free form. Members already written literally in
    the query are not returned. Order: group order, then member order; no duplicates.
    """
    settings = s or load_rag_settings()
    query = normalize_query(text, settings)
    folded = fold_accents(query) if settings.retrieval.accent_fold else None
    extra: list[str] = []
    for group in settings.retrieval.synonyms:
        members = [_nfc_fold(m) for m in group]
        hit = any(_contains(query, m) for m in members) or (
            folded is not None and any(_contains(folded, fold_accents(m)) for m in members)
        )
        if not hit:
            continue
        extra.extend(m for m in members if not _contains(query, m) and m not in extra)
    return extra
