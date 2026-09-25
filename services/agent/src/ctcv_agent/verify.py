"""Citation verification: does a chunk of an official guide support a claim? (brief §7).

E01 ships :class:`LexicalVerifier` (token overlap). E03 replaces it with the reranker
declared in ``config/models.yaml: rerank`` behind the same :class:`CitationVerifier`
protocol; the LLM-judge only runs offline in ``make eval`` (E05, F05).

ADR-007 adds the numeric layer: :func:`verify` also requires every number of the claim to
occur in the chunks (:func:`ctcv_agent.numeric.numbers_supported`), and
:func:`evaluate_sentence` reports numbers and lexical support separately for the answer
engine and the evaluation harness. :func:`has_foreign_script` rejects letters outside the
Latin script (the small composer model sometimes slips Chinese characters in).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ctcv_agent.guardrails import has_factual_claim
from ctcv_agent.numeric import numbers_supported
from ctcv_core.config import load_config

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# Function words that carry no factual content; ignored when scoring a claim.
STOPWORDS: frozenset[str] = frozenset(
    {
        "là", "và", "của", "có", "được", "cho", "các", "những", "với", "này", "đó",
        "thì", "mà", "để", "từ", "theo", "bác", "cháu", "nhé", "ạ", "một", "trên",
        "trong", "khi", "sẽ", "đã", "về", "hay", "hoặc", "rồi", "vào", "ra", "the",
        "a", "an", "of", "to", "in", "is",
    }
)  # fmt: skip


class CitationVerifier(Protocol):
    """Scores how well ``chunk`` supports ``claim`` in [0, 1]."""

    def score(self, claim: str, chunk: str) -> float:
        """Return a support score between 0 (unsupported) and 1 (fully supported)."""
        ...


def tokenize(text: str) -> set[str]:
    """Lower-case content tokens of ``text`` (≥ 2 characters, stopwords removed)."""
    return {
        t
        for t in (m.group(0).casefold() for m in _TOKEN_RE.finditer(text))
        if len(t) >= 2 and t not in STOPWORDS
    }


class LexicalVerifier:
    """Share of the claim's content tokens that also occur in the chunk."""

    def score(self, claim: str, chunk: str) -> float:
        """Return ``|claim ∩ chunk| / |claim|`` over content tokens (0 when the claim is empty)."""
        claim_tokens = tokenize(claim)
        if not claim_tokens:
            return 0.0
        overlap = len(claim_tokens & tokenize(chunk))
        return round(overlap / len(claim_tokens), 4)


def default_threshold() -> float:
    """Support score below which a citation is rejected (``guardrails.escalate_confidence``)."""
    return float(load_config("guardrails")["escalate_confidence"])


def verify(
    claim: str,
    chunks: Sequence[str],
    verifier: CitationVerifier | None = None,
    threshold: float | None = None,
) -> tuple[float, bool]:
    """Score ``claim`` against every chunk and return ``(best_score, ok)``.

    ``ok`` is True when the best score reaches the threshold from config (or the one
    given) **and** every number of the claim occurs in at least one chunk. An empty
    ``chunks`` sequence yields ``(0.0, False)``.
    """
    active = verifier or LexicalVerifier()
    limit = default_threshold() if threshold is None else threshold
    best = max((active.score(claim, chunk) for chunk in chunks), default=0.0)
    return best, best >= limit and numbers_supported(claim, chunks).ok


class _HasText(Protocol):
    text: str


@dataclass(frozen=True)
class SentenceVerdict:
    """How well a sentence is backed by its cited chunks.

    ``lexical_ok`` is only demanded of factual sentences (``has_factual_claim``); a sentence
    without facts is lexically ok whatever its score.
    """

    numbers_ok: bool
    unsupported_numbers: tuple[str, ...]
    lexical_score: float
    lexical_ok: bool
    factual: bool

    @property
    def ok(self) -> bool:
        """True when both the numbers and the wording are supported."""
        return self.numbers_ok and self.lexical_ok


def _texts(chunks: Sequence[str | _HasText]) -> list[str]:
    return [c if isinstance(c, str) else c.text for c in chunks]


def evaluate_sentence(
    sentence: str, chunks: Sequence[str | _HasText], lexical_min: float
) -> SentenceVerdict:
    """Check ``sentence`` against the cited ``chunks`` (strings or objects with ``.text``).

    Numbers must all occur in the chunks; the lexical score is the share of the sentence's
    content tokens found in the chunks taken together.
    """
    texts = _texts(chunks)
    numbers = numbers_supported(sentence, texts)
    score = LexicalVerifier().score(sentence, "\n".join(texts)) if texts else 0.0
    factual = has_factual_claim(sentence)
    return SentenceVerdict(
        numbers_ok=numbers.ok,
        unsupported_numbers=numbers.unsupported,
        lexical_score=score,
        lexical_ok=(not factual) or score >= lexical_min,
        factual=factual,
    )


def has_foreign_script(text: str) -> bool:
    """True when ``text`` contains a letter outside the Latin script (Vietnamese is Latin)."""
    normalized = unicodedata.normalize("NFC", text)
    return any(ch.isalpha() and "LATIN" not in unicodedata.name(ch, "") for ch in normalized)
