"""Step 8 — build_eval_sets: deterministic TTHC evaluation questions (ADR-007 C8).

Reads ``<clean>/tthc/records/*.json`` and writes ``<root>/eval/sets/samples/qa_tthc.jsonl``:

* at most two questions per procedure, taken in the order fee (when the record states an
  amount in ``phi_vnd``), time limit (``thoi_han``), documents (``thanh_phan_ho_so``);
* fee questions are **dropped** for records that ``normalize`` flagged ``phi_khong_ro`` or
  ``phi_bat_thuong`` (``normalize_report.json``): their amount needs a human check, so no
  gold value can be trusted;
* four natural Vietnamese phrasings per intent, picked by a stable hash of the procedure id;
* at most :data:`MAX_QUESTIONS` rows (first question of every procedure first, second
  questions in hash order), 10 % of them rewritten without diacritics (``kind:
  no_diacritics``);
* ``expected_values`` copied from structured fields (``"20.000"``, ``"07 Ngày làm việc"``,
  a form code such as ``"CT01"`` or the first words of the first document); a time limit
  longer than :data:`MAX_TIME_CHARS` lists several cases in one paragraph, has no single
  gold value and gets no question;
* ``split`` = ``dev`` when ``int(sha256(gold_procedure_id), 16) % 10 < 3``: both questions of
  one procedure land in the same split, so no procedure leaks between dev and test.

No model is called; the output is byte-for-byte reproducible. Every row is validated
against ``eval/sets/samples/qa_tthc.schema.json`` before writing.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ctcv_agent.rag.query import fold_accents
from ctcv_agent.rag.types import ProcedureRecord
from ctcv_core.config import validate_against_schema
from ctcv_data.pipeline import PipelineConfig, StepReport

STEP = "build_eval_sets"
SOURCE = "generated:tthc-template/1"
MAX_QUESTIONS = 130
MAX_PER_PROCEDURE = 2
NO_DIACRITICS_SHARE = 10  # one row in ten
DEV_BUCKETS = 3  # hash % 10 < 3 → dev
FLAG_CODES = frozenset({"phi_khong_ro", "phi_bat_thuong"})
SAMPLES_DIR = ("eval", "sets", "samples")
OUT_NAME = "qa_tthc.jsonl"
SCHEMA_NAME = "qa_tthc.schema.json"
DOC_PREFIX_WORDS = 6
MAX_TIME_CHARS = 80
NO_RECORDS = "chưa có bản ghi TTHC — chạy crawl --online rồi normalize trước"

TEMPLATES: dict[str, tuple[str, ...]] = {
    "phi_le_phi": (
        "Thủ tục {ten} mất bao nhiêu tiền?",
        "Lệ phí {ten} là bao nhiêu?",
        "Làm {ten} thì tốn bao nhiêu tiền?",
        "Cho hỏi phí {ten} hết bao nhiêu?",
    ),
    "thoi_han": (
        "Thủ tục {ten} mất bao lâu thì xong?",
        "Làm {ten} bao lâu thì có kết quả?",
        "Thời hạn giải quyết thủ tục {ten} là mấy ngày?",
        "Nộp hồ sơ {ten} rồi bao giờ có kết quả?",
    ),
    "thanh_phan_ho_so": (
        "Làm {ten} cần những giấy tờ gì?",
        "Thủ tục {ten} thì hồ sơ gồm những gì?",
        "Đi {ten} cần mang theo giấy tờ gì?",
        "Muốn {ten} thì phải chuẩn bị giấy tờ gì?",
    ),
}
SHORT_INTENT = {"phi_le_phi": "phi", "thoi_han": "thoihan", "thanh_phan_ho_so": "giayto"}
_CLAUSE_END_RE = re.compile(r"[.;:(]")
_LIST_MARK_RE = re.compile(r"^\s*(?:[-+•*]|\(?[a-zđ0-9]{1,2}[).])\s+", re.IGNORECASE)


def _hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def split_of(key: str) -> str:
    """``dev`` when ``int(sha256(key), 16) % 10 < 3``, else ``test``."""
    return "dev" if _hash(key) % 10 < DEV_BUCKETS else "test"


def _vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def _lower_first(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) >= 2 and flat[0].isupper() and flat[1].islower():
        return flat[0].lower() + flat[1:]
    return flat


# ----------------------------------------------------------------------------- expected values
def fee_values(record: ProcedureRecord) -> list[str]:
    """Distinct stated amounts of every channel, in record order (``"20.000"``)."""
    amounts = [a for c in record.cach_thuc for a in c.phi_vnd]
    return [_vnd(a) for a in dict.fromkeys(amounts)]


def time_values(record: ProcedureRecord) -> list[str]:
    """Distinct ``thoi_han`` texts, verbatim; none when one is a long case-by-case text."""
    texts = [" ".join(c.thoi_han.split()) for c in record.cach_thuc if c.thoi_han]
    if any(len(t) > MAX_TIME_CHARS for t in texts):
        return []  # several cases in one paragraph: no single gold value
    return list(dict.fromkeys(t for t in texts if t))


def doc_values(record: ProcedureRecord) -> list[str]:
    """Most frequent form code, else the first words of the first general document."""
    codes = [d.mau for d in record.thanh_phan_ho_so if d.mau]
    if codes:
        return [max(dict.fromkeys(codes), key=codes.count)]
    docs = record.thanh_phan_ho_so
    if not docs:
        return []
    first = next((d for d in docs if d.truong_hop is None), docs[0])
    name = _LIST_MARK_RE.sub("", " ".join(first.ten_giay_to.split()))
    clause = _CLAUSE_END_RE.split(name, maxsplit=1)[0]
    words = clause.strip(" ,-–").split()[:DOC_PREFIX_WORDS]
    return [" ".join(words)] if words else []


VALUE_FNS: dict[str, Callable[[ProcedureRecord], list[str]]] = {
    "phi_le_phi": fee_values,
    "thoi_han": time_values,
    "thanh_phan_ho_so": doc_values,
}


# ----------------------------------------------------------------------------- questions
def flagged_matts(report_path: Path) -> set[str]:
    """``matt`` of records whose fee ``normalize`` flagged (``<matt>: <code>: …`` warnings)."""
    if not report_path.is_file():
        return set()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for warning in report.get("warnings", []):
        parts = [p.strip() for p in str(warning).split(":", 2)]
        if len(parts) >= 2 and parts[1] in FLAG_CODES:
            found.add(parts[0])
    return found


def intents_for(record: ProcedureRecord, flagged: set[str]) -> list[str]:
    """Intents with a gold value, in priority order, at most two."""
    chosen = []
    for intent, values in VALUE_FNS.items():
        if intent == "phi_le_phi" and record.meta.matt in flagged:
            continue
        if values(record):
            chosen.append(intent)
    return chosen[:MAX_PER_PROCEDURE]


def make_row(record: ProcedureRecord, intent: str) -> dict[str, Any]:
    """One C8 row (kind ``field``) for ``record`` and ``intent``."""
    pid = record.procedure_id
    options = TEMPLATES[intent]
    template = options[_hash(f"{pid}:{intent}") % len(options)]
    values = VALUE_FNS[intent](record)
    return {
        "id": f"g-{pid}-{SHORT_INTENT[intent]}",
        "split": split_of(pid),
        "kind": "field",
        "question": template.format(ten=_lower_first(record.ten)),
        "expect": "answer",
        "gold_procedure_id": pid,
        "gold_intent": intent,
        "expected_values": values,
        "source": SOURCE,
        "notes": f"Sinh từ bản ghi {pid} (matt {record.meta.matt}), trường {intent}.",
    }


def select_rows(records: list[ProcedureRecord], flagged: set[str]) -> list[dict[str, Any]]:
    """First question of every procedure, then second questions in hash order, capped."""
    firsts: list[dict[str, Any]] = []
    seconds: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda r: r.procedure_id):
        rows = [make_row(record, intent) for intent in intents_for(record, flagged)]
        firsts.extend(rows[:1])
        seconds.extend(rows[1:])
    seconds.sort(key=lambda row: _hash(row["id"]))
    return (firsts + seconds)[:MAX_QUESTIONS]


def fold_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rewrite ``len // 10`` rows (lowest hash of ``nd:<id>``) without diacritics."""
    count = len(rows) // NO_DIACRITICS_SHARE
    picked = {r["id"] for r in sorted(rows, key=lambda r: _hash(f"nd:{r['id']}"))[:count]}
    for row in rows:
        if row["id"] in picked:
            row["kind"] = "no_diacritics"
            row["question"] = fold_accents(row["question"])
            row["notes"] += " Bản bỏ dấu."
    return sorted(rows, key=lambda r: r["id"])


# ----------------------------------------------------------------------------- step
def _clean_root(cfg: PipelineConfig) -> Path:
    clean = getattr(cfg, "clean", None)
    return Path(clean()) if callable(clean) else Path(cfg.root) / "data" / "clean"


def _write(rows: list[dict[str, Any]], root: Path) -> Path:
    samples = root.joinpath(*SAMPLES_DIR)
    schema = json.loads((samples / SCHEMA_NAME).read_text(encoding="utf-8"))
    for row in rows:
        validate_against_schema(row, schema, OUT_NAME)
    out = samples / OUT_NAME
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in rows)
    out.write_bytes(text.encode("utf-8"))
    return out


def run(cfg: PipelineConfig) -> StepReport:
    """Build ``eval/sets/samples/qa_tthc.jsonl`` from the clean TTHC records."""
    tthc = _clean_root(cfg) / "tthc"
    paths = sorted((tthc / "records").glob("*.json"))
    if not paths:
        return StepReport(STEP, "skipped", NO_RECORDS)
    records = [ProcedureRecord.load(p) for p in paths]
    flagged = flagged_matts(tthc / "normalize_report.json")
    rows = fold_share(select_rows(records, flagged))
    out = _write(rows, Path(cfg.root))
    dropped = sum(1 for r in records if r.meta.matt in flagged and fee_values(r))
    details = {
        "records": len(records),
        "rows": len(rows),
        "fee_flagged_dropped": dropped,
        "by_intent": {i: sum(r["gold_intent"] == i for r in rows) for i in TEMPLATES},
        "no_diacritics": sum(r["kind"] == "no_diacritics" for r in rows),
        "split": {s: sum(r["split"] == s for r in rows) for s in ("dev", "test")},
    }
    message = f"{len(rows)} câu hỏi từ {len(records)} bản ghi"
    return StepReport(STEP, "ok", message, details, [out.relative_to(cfg.root).as_posix()])
