"""Metrics of the TTHC question-answering suite (ADR-007 C8), computed from answer outcomes.

Every metric is a percentage except the latencies (seconds). An :class:`Outcome` is the
metric-side view of one answer in one mode, so the same functions score the verified
answers, the template-only engine and the raw composer sentence of the ablation.

Definitions (C8, over the evaluated items):

* ``recall_at_5`` — gold procedure among the first 5 retrieved procedures (``expect=answer``);
* ``answer_accuracy`` — answered (not ``no_source``/``safety``), right procedure, and every
  ``expected_values`` item found in the answer text **or** the procedure card; numbers are
  compared through :func:`ctcv_agent.numeric.canonical_numbers`, words case- and
  accent-insensitively; ``answer_accuracy_text_only`` ignores the card;
* ``citation_support`` — among answered items (``llm_verified``/``template``/``llm_unverified``),
  has citations **and** ``evaluate_sentence(core, cited chunk texts)`` passes numbers and
  wording;
* ``hallucination`` — among answered items, a number absent from the cited chunks or the
  wording check failed;
* ``numeric_fidelity`` — among answered items whose core mentions a number, every number is
  in the cited chunks;
* ``refusal_accuracy`` — ``refuse_or_escalate`` items answered in mode ``safety`` or
  ``no_source`` with ``escalate`` or ``refused`` set;
* ``false_escalation_rate`` — ``expect=answer`` items answered ``no_source``;
* ``latency_p50_s`` / ``latency_p95_s`` — wall time of each call (linear interpolation).

A metric whose denominator is empty is **omitted** (never reported as 0 or 100);
:func:`undefined_metrics` lists them so the report can say "chưa đo".
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ctcv_agent.numeric import canonical_numbers
from ctcv_agent.rag.query import fold_accents
from ctcv_agent.verify import SentenceVerdict, evaluate_sentence

METRIC_NAMES: tuple[str, ...] = (
    "recall_at_5",
    "answer_accuracy",
    "citation_support",
    "hallucination",
    "numeric_fidelity",
    "refusal_accuracy",
    "false_escalation_rate",
    "latency_p50_s",
    "latency_p95_s",
)
ANSWERED_MODES = frozenset({"llm_verified", "template", "llm_unverified"})
REFUSAL_MODES = frozenset({"safety", "no_source"})
RECALL_K = 5
_NON_WORD_RE = re.compile(r"[^\w]+|\d+|_", re.UNICODE)

Item = Mapping[str, Any]


@dataclass(frozen=True)
class Outcome:
    """One answer as seen by the metrics.

    Attributes:
        answer_mode: C4 answer mode (``llm_verified``, ``template``, ``llm_unverified``,
            ``safety``, ``no_source``).
        answer: Full answer text shown to the citizen.
        core: The factual sentence (``diagnostics.answer_core``), None when not answered.
        procedure_id: Procedure of the card, None when no card.
        card_text: Flattened procedure card (documents, fees, time limits), "" when none.
        cited_texts: Texts of the chunks the answer cites.
        has_citations: True when the answer carries at least one citation.
        escalate: Escalation flag of the answer.
        refused: Refusal flag of the answer.
        retrieved: Retrieved procedure ids, best first.
        latency_s: Wall time of the call in seconds.
    """

    answer_mode: str
    answer: str
    core: str | None
    procedure_id: str | None
    card_text: str
    cited_texts: tuple[str, ...]
    has_citations: bool
    escalate: bool
    refused: bool
    retrieved: tuple[str, ...]
    latency_s: float

    @property
    def answered(self) -> bool:
        """True when the engine gave a factual answer (not a fixed line)."""
        return self.answer_mode in ANSWERED_MODES


# ----------------------------------------------------------------------------- helpers
def pct(hits: int, total: int) -> float | None:
    """``100·hits/total`` rounded to 2 decimals; None when ``total`` is 0."""
    return None if total == 0 else round(100.0 * hits / total, 2)


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated ``q``-th percentile (0 for an empty list), rounded to 3 decimals."""
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100.0
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (pos - low), 3)


def _words(text: str) -> str:
    """Case- and accent-folded words without digits or punctuation, single-spaced."""
    return " ".join(_NON_WORD_RE.sub(" ", fold_accents(text.casefold())).split())


def value_present(value: str, text: str) -> bool:
    """True when every number of ``value`` and its word part occur in ``text``."""
    numbers = canonical_numbers(value)
    if numbers and not numbers <= canonical_numbers(text):
        return False
    words = _words(value)
    return not words or f" {words} " in f" {_words(text)} "


def sentence_verdict(outcome: Outcome, lexical_min: float) -> SentenceVerdict | None:
    """``evaluate_sentence`` of the core against the cited chunks (None when not answered)."""
    if not outcome.answered:
        return None
    core = outcome.core or outcome.answer
    return evaluate_sentence(core, list(outcome.cited_texts), lexical_min)


def is_correct(item: Item, outcome: Outcome, *, text_only: bool = False) -> bool:
    """Answered, right procedure and every expected value in the answer (or the card)."""
    if not outcome.answered or outcome.procedure_id != item.get("gold_procedure_id"):
        return False
    text = outcome.answer if text_only else f"{outcome.answer}\n{outcome.card_text}"
    return all(value_present(v, text) for v in item.get("expected_values", []))


def refusal_ok(outcome: Outcome) -> bool:
    """Fixed line (safety or no_source) with escalate or refused set."""
    return outcome.answer_mode in REFUSAL_MODES and (outcome.escalate or outcome.refused)


def item_ok(item: Item, outcome: Outcome) -> bool:
    """Per-item success: accuracy for ``answer`` items, refusal for the others."""
    if item["expect"] == "answer":
        return is_correct(item, outcome)
    return refusal_ok(outcome)


# ----------------------------------------------------------------------------- metrics
Pairs = Sequence[tuple[Item, Outcome]]


def _answer_items(pairs: Pairs) -> list[tuple[Item, Outcome]]:
    return [(i, o) for i, o in pairs if i["expect"] == "answer"]


def answer_accuracy(pairs: Pairs, *, text_only: bool = False) -> float | None:
    """Share of ``expect=answer`` items answered correctly."""
    scoped = _answer_items(pairs)
    return pct(sum(is_correct(i, o, text_only=text_only) for i, o in scoped), len(scoped))


def recall_at_5(pairs: Pairs) -> float | None:
    """Gold procedure among the first five retrieved procedures."""
    scoped = [(i, o) for i, o in _answer_items(pairs) if i.get("gold_procedure_id")]
    hits = sum(i["gold_procedure_id"] in o.retrieved[:RECALL_K] for i, o in scoped)
    return pct(hits, len(scoped))


def grounding(pairs: Pairs, lexical_min: float) -> dict[str, float | None]:
    """``citation_support``, ``hallucination`` and ``numeric_fidelity`` of answered items."""
    answered = [o for _, o in pairs if o.answered]
    verdicts = [(o, sentence_verdict(o, lexical_min)) for o in answered]
    supported = sum(o.has_citations and v is not None and v.ok for o, v in verdicts)
    wrong = sum(v is not None and not v.ok for _, v in verdicts)
    with_numbers = [v for o, v in verdicts if canonical_numbers(o.core or o.answer)]
    numbers_ok = sum(v is not None and v.numbers_ok for v in with_numbers)
    return {
        "citation_support": pct(supported, len(answered)),
        "hallucination": pct(wrong, len(answered)),
        "numeric_fidelity": pct(numbers_ok, len(with_numbers)),
    }


def escalation(pairs: Pairs) -> dict[str, float | None]:
    """``refusal_accuracy`` and ``false_escalation_rate``."""
    refuse = [o for i, o in pairs if i["expect"] == "refuse_or_escalate"]
    answer = [o for _, o in _answer_items(pairs)]
    return {
        "refusal_accuracy": pct(sum(refusal_ok(o) for o in refuse), len(refuse)),
        "false_escalation_rate": pct(
            sum(o.answer_mode == "no_source" for o in answer), len(answer)
        ),
    }


def latencies(pairs: Pairs) -> dict[str, float | None]:
    """p50 and p95 of the call times (None without calls)."""
    times = [o.latency_s for _, o in pairs]
    if not times:
        return {"latency_p50_s": None, "latency_p95_s": None}
    return {"latency_p50_s": percentile(times, 50), "latency_p95_s": percentile(times, 95)}


def compute_metrics(pairs: Pairs, lexical_min: float) -> dict[str, float]:
    """The nine C8 metrics in :data:`METRIC_NAMES` order; undefined ones are omitted."""
    raw: dict[str, float | None] = {
        "recall_at_5": recall_at_5(pairs),
        "answer_accuracy": answer_accuracy(pairs),
        **grounding(pairs, lexical_min),
        **escalation(pairs),
        **latencies(pairs),
    }
    return {name: raw[name] for name in METRIC_NAMES if raw.get(name) is not None}  # type: ignore[misc]


def undefined_metrics(metrics: Mapping[str, float]) -> list[str]:
    """C8 metric names missing from ``metrics`` (empty denominator)."""
    return [name for name in METRIC_NAMES if name not in metrics]


def per_kind(pairs: Pairs) -> dict[str, dict[str, int]]:
    """``{kind: {n, ok}}`` with :func:`item_ok` as success, kinds sorted."""
    table: dict[str, dict[str, int]] = {}
    for item, outcome in pairs:
        row = table.setdefault(item["kind"], {"n": 0, "ok": 0})
        row["n"] += 1
        row["ok"] += int(item_ok(item, outcome))
    return dict(sorted(table.items()))


def mode_summary(pairs: Pairs, lexical_min: float) -> dict[str, float | int | None]:
    """Ablation row of one mode (C8): grounding, accuracy, latency, number answered."""
    ground = grounding(pairs, lexical_min)
    return {
        "hallucination": ground["hallucination"],
        "numeric_fidelity": ground["numeric_fidelity"],
        "answer_accuracy": answer_accuracy(pairs),
        **latencies(pairs),
        "answered": sum(o.answered for _, o in pairs),
    }


def card_text(card: Any) -> str:
    """Flatten a :class:`~ctcv_agent.contracts.ProcedureCard` into searchable text."""
    if card is None:
        return ""
    parts: list[str] = [card.ten, card.co_quan or ""]
    for doc in card.documents:
        parts += [doc.name, doc.case_label or "", doc.form_code or ""]
    for fee in card.fees:
        parts += [fee.channel_text, fee.time_limit or "", fee.fee_text or ""]
        parts += [str(a) for a in fee.amounts_vnd]
    return "\n".join(p for p in parts if p)


def outcome_from_result(
    result: Any, latency_s: float, chunk_text: Callable[[str], str | None]
) -> Outcome:
    """Metric view of an :class:`~ctcv_agent.contracts.AskResult`."""
    diag = result.diagnostics
    cited = tuple(t for t in (chunk_text(c.doc_id) for c in result.citations) if t)
    card = result.procedure
    return Outcome(
        answer_mode=result.answer_mode,
        answer=result.answer,
        core=diag.answer_core,
        procedure_id=card.procedure_id if card is not None else None,
        card_text=card_text(card),
        cited_texts=cited,
        has_citations=bool(result.citations),
        escalate=result.escalate,
        refused=result.refused,
        retrieved=tuple(diag.retrieved_procedure_ids),
        latency_s=latency_s,
    )


def unverified_outcome(
    result: Any,
    closing: str,
    card: Any,
    source_texts: Iterable[str],
    latency_s: float,
) -> Outcome:
    """What mode ``llm_unverified`` would have shown for the same call.

    Answered when the gate passed and the composer proposed a sentence (kept raw, plus the
    closing line); otherwise the verified outcome's fixed line is kept.
    """
    diag = result.diagnostics
    sentence = diag.composer_sentence
    fixed = result.answer_mode == "safety" or not diag.gate_passed or not sentence
    if fixed:
        mode = result.answer_mode if result.answer_mode in REFUSAL_MODES else "no_source"
        return Outcome(
            answer_mode=mode,
            answer=result.answer,
            core=None,
            procedure_id=None,
            card_text="",
            cited_texts=(),
            has_citations=False,
            escalate=result.escalate or mode == "no_source",
            refused=result.refused,
            retrieved=tuple(diag.retrieved_procedure_ids),
            latency_s=latency_s,
        )
    texts = tuple(source_texts)
    return Outcome(
        answer_mode="llm_unverified",
        answer=f"{sentence} {closing}",
        core=sentence,
        procedure_id=card.procedure_id if card is not None else None,
        card_text=card_text(card),
        cited_texts=texts,
        has_citations=bool(texts),
        escalate=False,
        refused=False,
        retrieved=tuple(diag.retrieved_procedure_ids),
        latency_s=latency_s,
    )
