"""What a citizen asks about a procedure: fee, time limit, documents… (ADR-007 C5 ``intents``).

``detect_intent`` walks ``config/rag.yaml: intents`` in key order (key order = priority) and
returns the first intent one of whose phrases occurs as whole words in the normalised
question; no match means ``tong_quan`` (overview).

Matching is accent-tolerant syllable by syllable: an unaccented syllable of the question may
stand for an accented one of the phrase (``"le phi"`` finds ``"lệ phí"``), but an accented
syllable must match exactly, so ``"màu"`` (colour) never counts as ``"mẫu"`` (form).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ctcv_agent.rag.query import fold_accents, normalize_query
from ctcv_agent.rag.settings import RagSettings

FALLBACK_INTENT = "tong_quan"


def _syllable_pattern(syllable: str) -> str:
    """Regex for one syllable: itself, or its accent-free form when that differs."""
    folded = fold_accents(syllable)
    if folded == syllable:
        return re.escape(syllable)
    return f"(?:{re.escape(syllable)}|{re.escape(folded)})"


@lru_cache(maxsize=512)
def phrase_regex(phrase: str) -> re.Pattern[str]:
    """Compile ``phrase`` into a whole-word, accent-tolerant, case-insensitive pattern."""
    normalized = unicodedata.normalize("NFC", phrase).casefold().split()
    body = r"\s+".join(_syllable_pattern(s) for s in normalized)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def detect_intent(question: str, settings: RagSettings) -> str:
    """Return the highest-priority intent whose phrase occurs in ``question``.

    Args:
        question: The (already PII-redacted) citizen question.
        settings: Resolved RAG settings (``intents`` in priority order).
    """
    normalized = normalize_query(question, settings)
    for intent, phrases in settings.intents.items():
        if any(phrase_regex(p).search(normalized) for p in phrases):
            return intent
    return FALLBACK_INTENT
