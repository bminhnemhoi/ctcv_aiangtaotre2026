"""Okapi BM25 over Vietnamese syllables, adjacent-syllable bigrams and accent-free forms.

Vietnamese words are written as space-separated syllables ("đăng ký", "thường trú"), so a
chunk is indexed by its syllables plus every adjacent pair (``đăng_ký``) — the bigrams give
multi-syllable words their own weight without a word segmenter. With ``accent_fold`` the
accent-free form of every token is added as well (``lệ_phí`` → ``le_phi``), so a question
typed without diacritics still matches. Pure Python, no numpy: postings lists make a query
cost proportional to the documents that share its terms.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence

from ctcv_agent.rag.query import content_tokens, fold_accents, syllable_bigrams


def tokenize_for_bm25(text: str, accent_fold: bool) -> list[str]:
    """Return BM25 terms of ``text``: syllables, adjacent bigrams, then accent-free forms.

    Stopwords are removed before bigrams are formed. Accent-free terms are only added when
    they differ from the original (``"cmnd"`` is not counted twice).

    Args:
        text: Chunk text or normalised query.
        accent_fold: Add the accent-free variants (``config/rag.yaml: retrieval.accent_fold``).
    """
    tokens = content_tokens(text)
    terms = [*tokens, *syllable_bigrams(tokens)]
    if not accent_fold:
        return terms
    folded = [fold_accents(token) for token in tokens]
    terms.extend(f for f, t in zip(folded, tokens, strict=True) if f != t)
    original_pairs = syllable_bigrams(tokens)
    folded_pairs = syllable_bigrams(folded)
    terms.extend(f for f, t in zip(folded_pairs, original_pairs, strict=True) if f != t)
    return terms


class BM25Index:
    """Okapi BM25 (Lucene idf ``ln(1 + (N - df + 0.5) / (df + 0.5))``) over token lists.

    Args:
        docs_tokens: One token list per document, in index order.
        k1: Term-frequency saturation (≥ 0).
        b: Length normalisation strength in [0, 1].

    Raises:
        ValueError: when ``k1`` or ``b`` is out of range.
    """

    def __init__(self, docs_tokens: Iterable[Sequence[str]], k1: float, b: float) -> None:
        """Build postings lists, document lengths and idf values."""
        if k1 < 0:
            raise ValueError(f"k1 phải ≥ 0, nhận được {k1}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b phải trong [0, 1], nhận được {b}")
        self._k1 = float(k1)
        self._b = float(b)
        self._lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for doc_index, tokens in enumerate(docs_tokens):
            self._lengths.append(len(tokens))
            for term, tf in Counter(tokens).items():
                self._postings.setdefault(term, []).append((doc_index, tf))
        count = len(self._lengths)
        self._avgdl = (sum(self._lengths) / count) if count else 0.0
        self._idf = {
            term: math.log(1.0 + (count - len(p) + 0.5) / (len(p) + 0.5))
            for term, p in self._postings.items()
        }

    def __len__(self) -> int:
        """Number of indexed documents."""
        return len(self._lengths)

    def _norm(self, doc_index: int) -> float:
        """Length-normalised ``k1`` factor of one document."""
        ratio = self._lengths[doc_index] / self._avgdl if self._avgdl else 0.0
        return self._k1 * (1.0 - self._b + self._b * ratio)

    def scores(self, query_tokens: Iterable[str]) -> list[float]:
        """Return the BM25 score of every document for the distinct ``query_tokens``."""
        out = [0.0] * len(self._lengths)
        for term in dict.fromkeys(query_tokens):
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf[term]
            for doc_index, tf in postings:
                out[doc_index] += idf * tf * (self._k1 + 1.0) / (tf + self._norm(doc_index))
        return out
