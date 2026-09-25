"""Step 2 — normalize: raw TTHC pages → schema-valid records (ADR-007 C1/C2, offline).

Reads ``data/raw/tthc/manifest.jsonl`` (written by ``crawl --online``), parses every saved
procedure page with :mod:`ctcv_data.tthc_bca`, validates the record against
``config/schemas/tthc-record.schema.json`` and writes ``<clean>/tthc/records/<procedure_id>.json``
(UTF-8, indent 2). A repeated ``procedure_id`` keeps the first page and logs a warning. The run
summary goes to ``<clean>/tthc/normalize_report.json``; records from a previous run that are
not produced again are removed, so the directory always mirrors the current manifest.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from ctcv_agent.rag.types import PARSER_VERSION
from ctcv_core.config import schema_path
from ctcv_core.errors import ValidationFailed
from ctcv_data import tthc_bca
from ctcv_data.pipeline import PipelineConfig, StepReport
from ctcv_data.sources import SourcesConfig, load_sources

STEP = "normalize"
NO_RAW = "chưa có dữ liệu thô TTHC — chạy crawl --online trước"
TTHC_DIRNAME = "tthc"
RAW_PAGES_DIRNAME = "bca"
RECORDS_DIRNAME = "records"
REPORT_NAME = "normalize_report.json"
REVIEW_NAME = "review_flagged.html"
REVIEW_LIMIT = 30
SEED_MARK = "/bocongan/bothutuc"
COVERAGE_FIELDS = (
    "cach_thuc",
    "phi_vnd",
    "thanh_phan_ho_so",
    "trinh_tu",
    "can_cu_phap_ly",
    "bieu_mau",
)


@dataclass
class _Run:
    """Accumulates the outcome of one normalize run."""

    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    invalid: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_detail: int = 0
    flags: dict[str, dict[str, Any]] = field(default_factory=dict)

    def flag(self, row: dict[str, Any], reasons: list[str], record: dict | None = None) -> None:
        """Remember a page a person should look at (for ``review_flagged.html``)."""
        entry = self.flags.setdefault(str(row["matt"]), {"url": row["url"], "reasons": []})
        entry["reasons"].extend(reasons)
        if record is not None:
            entry["record"] = record


def min_request_interval(stamps: list[str]) -> float | None:
    """Smallest gap in seconds between any two ``fetched_at`` stamps (``None`` if < 2)."""
    moments = sorted(dt.datetime.fromisoformat(s.replace("Z", "+00:00")) for s in stamps)
    gaps = [(b - a).total_seconds() for a, b in zip(moments, moments[1:], strict=False)]
    return round(min(gaps), 3) if gaps else None


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _source_meta(sources: SourcesConfig, row: dict[str, Any]) -> dict[str, Any]:
    """Portal name, issuing agency and licence note from ``sources.yaml`` for one page."""
    seeds = [s for s in sources.sources if SEED_MARK in s.url]
    code = row.get("linh_vuc_code")
    seed = next((s for s in seeds if f"linh_vuc={code}&" in s.url + "&"), seeds[0])
    domain = sources.domain_for(row["url"])
    return {
        "source_url": row["url"],
        "source_portal": seed.agency,
        "agency": domain.agency if domain else seed.agency,
        "matt": str(row["matt"]),
        "linh_vuc_code": code,
        "fetched_at": row["fetched_at"],
        "sha256_raw": row["sha256_raw"],
        "license_note": seed.license_note,
        "name": row.get("name"),
    }


def _schema_errors(record: dict[str, Any], validator: jsonschema.Validator) -> list[str]:
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<gốc>'}: {e.message}" for e in errors]


def _normalize_page(
    row: dict[str, Any],
    page: Path,
    sources: SourcesConfig,
    validator: jsonschema.Validator,
    run: _Run,
) -> None:
    """Parse, validate and keep one saved detail page (or log why it was rejected)."""
    matt = str(row["matt"])
    body = page.read_bytes() if page.is_file() else b""
    if hashlib.sha256(body).hexdigest() != row["sha256_raw"]:
        run.invalid.append({"matt": matt, "errors": ["sha256_raw khác nội dung file đã lưu"]})
        run.flag(row, run.invalid[-1]["errors"])
        return
    warnings: list[str] = []
    parsed = tthc_bca.parse_detail(body.decode("utf-8", errors="replace"))
    record = tthc_bca.to_record(parsed, _source_meta(sources, row), warnings=warnings)
    run.warnings.extend(f"{matt}: {w}" for w in warnings)
    errors = _schema_errors(record, validator)
    if errors:
        run.invalid.append({"matt": matt, "errors": errors[:10]})
        run.flag(row, ["không hợp lệ: " + e for e in errors[:3]])
        return
    pid = record["procedure_id"]
    if pid in run.records:
        kept = run.records[pid]["meta"]["matt"]
        run.warnings.append(f"procedure_id trùng {pid}: giữ matt {kept}, bỏ matt {matt}")
        run.flag(row, [run.warnings[-1]], record)
        return
    run.records[pid] = record
    if warnings:
        run.flag(row, warnings, record)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _coverage(records: list[dict[str, Any]]) -> dict[str, float]:
    counts = dict.fromkeys(COVERAGE_FIELDS, 0)
    for record in records:
        for name in COVERAGE_FIELDS:
            if name == "phi_vnd":
                counts[name] += any(c["phi_vnd"] for c in record["cach_thuc"])
            else:
                counts[name] += bool(record[name])
    return {name: _pct(count, len(records)) for name, count in counts.items()}


def _tally(records: list[dict[str, Any]], key: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in records:
        label = key(record) or "(không rõ)"
        out[label] = out.get(label, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _report(run: _Run, rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = list(run.records.values())
    return {
        "generated_at": dt.datetime.now(dt.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "parser_version": PARSER_VERSION,
        "pages_detail": run.pages_detail,
        "records_valid": len(records),
        "records_invalid": len(run.invalid),
        "invalid": run.invalid,
        "warnings": run.warnings,
        "coverage": _coverage(records),
        "coverage_extra": {
            "phi_le_phi": _pct(
                sum(any(c["phi_le_phi"] for c in r["cach_thuc"]) for r in records), len(records)
            ),
            "cap_thuc_hien": _pct(sum(bool(r["cap_thuc_hien"]) for r in records), len(records)),
        },
        "by_linh_vuc": _tally(records, lambda r: r["linh_vuc"]),
        "by_linh_vuc_code": _tally(records, lambda r: r["meta"]["linh_vuc_code"]),
        "min_request_interval_s": min_request_interval([r["fetched_at"] for r in rows]),
        "procedure_ids": sorted(run.records),
    }


def _content_changes(directory: Path, records: dict[str, dict[str, Any]]) -> list[str]:
    """Procedure ids whose ``sha256_content`` differs from the record left by the last run.

    The raw HTML hash changes on every fetch (CSRF token, cache-busting query strings), so the
    content hash is the signal that the procedure itself was edited on the portal.
    """
    changed: list[str] = []
    for pid, record in sorted(records.items()):
        path = directory / f"{pid}.json"
        if not path.is_file():
            continue
        try:
            old = json.loads(path.read_text(encoding="utf-8"))["meta"]["sha256_content"]
        except (ValueError, KeyError, TypeError):
            old = None
        if old != record["meta"]["sha256_content"]:
            changed.append(pid)
    return changed


def _write_records(directory: Path, records: dict[str, dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.json"):
        if stale.stem not in records:
            stale.unlink()
    for pid, record in records.items():
        text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        (directory / f"{pid}.json").write_text(text, encoding="utf-8")


_REVIEW_STYLE = (
    "body{font-family:sans-serif;max-width:60rem;margin:auto;padding:1rem}"
    ".flag{border:1px solid #ccc;border-radius:6px;padding:.5rem 1rem;margin:1rem 0}"
    ".why{color:#a40000}pre{white-space:pre-wrap;background:#f6f6f6;padding:.5rem}"
)


def _review_section(matt: str, flag: dict[str, Any]) -> str:
    record = flag.get("record") or {}
    raw = record.get("sections_raw", {})
    fees = [
        f"{c['kenh_text']}: {c['phi_le_phi']} {c['phi_vnd']}" for c in record.get("cach_thuc", [])
    ]
    title = html.escape(record.get("ten", "(không đọc được)"))
    url = html.escape(flag["url"])
    parts = [
        '<section class="flag">',
        f"<h2>matt {html.escape(matt)} — {title}</h2>",
        f'<p><a href="{url}">{url}</a></p>',
        "<ul>" + "".join(f'<li class="why">{html.escape(r)}</li>' for r in flag["reasons"]),
        "</ul>",
    ]
    if record:
        parts.append("<p>Phí đã lưu theo kênh:</p><pre>" + html.escape("\n".join(fees)) + "</pre>")
        for label in ("Phí", "Lệ Phí"):
            text = html.escape(raw.get(label, ""))
            parts.append(f"<p>Nguyên văn mục {label}:</p><pre>{text}</pre>")
    return "\n".join(parts) + "\n</section>"


def write_review_html(path: Path, flags: dict[str, dict[str, Any]]) -> Path:
    """Static page with at most ``REVIEW_LIMIT`` flagged pages for a person to check by hand."""
    chosen = list(flags.items())[:REVIEW_LIMIT]
    body = "\n".join(_review_section(matt, flag) for matt, flag in chosen)
    head = (
        '<!doctype html>\n<html lang="vi"><head><meta charset="utf-8">'
        f"<title>TTHC cần duyệt</title><style>{_REVIEW_STYLE}</style></head><body>"
        f"<h1>Trang thủ tục cần người duyệt ({len(chosen)}/{len(flags)})</h1>"
        "<p>Sinh bởi bước normalize. So nội dung đã lưu với trang gốc (bấm liên kết).</p>\n"
    )
    path.write_text(head + body + "\n</body></html>\n", encoding="utf-8")
    return path


def normalize_tthc(cfg: PipelineConfig) -> dict[str, Any]:
    """Normalize every saved detail page of the TTHC manifest; return the report dict."""
    rows = _read_manifest(cfg.raw() / TTHC_DIRNAME / "manifest.jsonl")
    sources = load_sources(cfg.root / "data" / "sources.yaml")
    schema = json.loads(schema_path("tthc-record", cfg.root).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    run = _Run()
    pages_dir = cfg.raw() / TTHC_DIRNAME / RAW_PAGES_DIRNAME
    for row in rows:
        if row.get("kind") != "detail" or row.get("http_status") != 200 or not row.get("path"):
            continue
        run.pages_detail += 1
        _normalize_page(row, pages_dir / f"tthc_{row['matt']}.html", sources, validator, run)
    out = cfg.clean() / TTHC_DIRNAME
    changed = _content_changes(out / RECORDS_DIRNAME, run.records)
    _write_records(out / RECORDS_DIRNAME, run.records)
    report = _report(run, rows) | {"flagged": len(run.flags), "content_changed": changed}
    (out / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_review_html(out / REVIEW_NAME, run.flags)
    return report


def run(cfg: PipelineConfig) -> StepReport:
    """Step entry point: skipped (exit 0) until ``crawl --online`` has produced raw pages."""
    if not (cfg.raw() / TTHC_DIRNAME / "manifest.jsonl").is_file():
        return StepReport(STEP, "skipped", NO_RAW)
    try:
        report = normalize_tthc(cfg)
    except (ValidationFailed, OSError, ValueError, KeyError) as exc:
        return StepReport(STEP, "failed", f"Chuẩn hóa TTHC lỗi: {exc}")
    out = cfg.clean() / TTHC_DIRNAME
    message = (
        f"{report['records_valid']} bản ghi hợp lệ / {report['pages_detail']} trang chi tiết, "
        f"{report['records_invalid']} không hợp lệ, {len(report['warnings'])} cảnh báo"
    )
    summary = {k: report[k] for k in ("records_valid", "records_invalid", "pages_detail")}
    summary |= {"coverage": report["coverage"], "by_linh_vuc_code": report["by_linh_vuc_code"]}
    summary["min_request_interval_s"] = report["min_request_interval_s"]
    summary["flagged"] = report["flagged"]
    outputs = [str(out / RECORDS_DIRNAME), str(out / REPORT_NAME), str(out / REVIEW_NAME)]
    return StepReport(STEP, "ok", message, summary, outputs)
