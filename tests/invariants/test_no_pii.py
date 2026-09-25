"""Invariant (b), brief §15: no PII in fixtures and no PII column in the database models.

Every ``*.json`` / ``*.jsonl`` / ``*.yaml`` / ``*.md`` under ``services/``, ``sandbox/``,
``drills/``, ``eval/`` and ``data/`` is scanned with the PII regexes declared in
``config/guardrails.yaml`` (CCCD, card number, OTP, phone, e-mail). Long hex digests
(sha256, uuid) are masked first so a checksum can never look like a phone number.
Git-ignored generated data directories (``data/raw`` and friends, ``eval/sets`` except
``samples``) are skipped: their PII policy is enforced by the pipeline that writes them.
Negative test fixtures (directories named ``invalid``, ``bad``, ``*_bad`` ...) are skipped
too: they exist precisely to prove that a validator rejects such content.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ctcv_core.config import find_repo_root, load_config

SCAN_ROOTS = ("services", "sandbox", "drills", "eval", "data")
EXTENSIONS = frozenset({".json", ".jsonl", ".yaml", ".md"})
SKIP_DIR_NAMES = frozenset(
    {"node_modules", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache", "htmlcov"}
)
SKIP_GENERATED = ("data/raw/", "data/clean/", "data/ui/", "data/sft/", "data/dpo/", "eval/sets/")
KEEP_GENERATED = ("eval/sets/samples/",)
# Red-team attack inputs must contain synthetic PII-shaped strings (fake OTP, phone, card
# numbers) or the guardrails could not be tested. Inputs are exempt; every OUTPUT the runner writes
# (eval/reports/*.md) stays scanned, so a leak of those strings still fails this invariant.
ATTACK_CORPORA = ("eval/redteam/",)
NEGATIVE_FIXTURE_DIR_RE = re.compile(r"^(?:invalid|bad|negative|rejected)$|_bad$|^bad_")
DIGEST_RE = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
PII_COLUMN_RE = re.compile(
    r"cccd|phone|otp|password|passwd|email|cvv|card_number|so_the|can_cuoc", re.IGNORECASE
)


def pii_regexes() -> list[tuple[str, re.Pattern[str]]]:
    """``(name, compiled regex)`` for every pattern in ``config/guardrails.yaml``."""
    return [(p["name"], re.compile(p["regex"])) for p in load_config("guardrails")["pii_patterns"]]


def fixture_files(root: Path) -> list[Path]:
    """Every fixture-like text file under the scanned roots, generated data excluded."""
    files: list[Path] = []
    for top in SCAN_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in EXTENSIONS or not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if any(NEGATIVE_FIXTURE_DIR_RE.match(part) for part in path.parent.parts):
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith(SKIP_GENERATED) and not rel.startswith(KEEP_GENERATED):
                continue
            if rel.startswith(ATTACK_CORPORA):
                continue
            files.append(path)
    return files


def scan_text(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[tuple[int, str]]:
    """``(line, pattern_name)`` for every PII match; the matched value is never returned."""
    masked = DIGEST_RE.sub("<digest>", text)
    hits: list[tuple[int, str]] = []
    for name, pattern in patterns:
        for match in pattern.finditer(masked):
            hits.append((masked.count("\n", 0, match.start()) + 1, name))
    return sorted(hits)


def test_scanner_detects_planted_pii(tmp_path: Path) -> None:
    patterns = pii_regexes()
    planted = tmp_path / "x.json"
    planted.write_text('{"phone": "0912345678", "otp": "mã OTP là 482913"}', encoding="utf-8")
    names = {name for _, name in scan_text(planted.read_text(encoding="utf-8"), patterns)}
    assert {"phone", "otp"} <= names
    assert scan_text("sha256: " + "a0123456789b" * 4, patterns) == []


def test_scan_is_not_vacuous() -> None:
    files = fixture_files(find_repo_root())
    assert files, "không tìm thấy fixture nào để quét"
    assert any(p.suffix == ".json" for p in files)


def test_fixtures_contain_no_pii() -> None:
    root = find_repo_root()
    patterns = pii_regexes()
    offenders: list[str] = []
    for path in fixture_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        offenders.extend(f"{rel}:{line}: {name}" for line, name in scan_text(text, patterns))
    assert not offenders, "Fixture chứa PII (file:dòng: loại):\n" + "\n".join(offenders)


def test_db_models_have_no_pii_columns() -> None:
    models = pytest.importorskip(
        "ctcv_api.models", reason="ctcv_api chưa cài được — bỏ qua kiểm tra cột DB"
    )
    tables = models.Base.metadata.tables
    assert tables, "ctcv_api.models không khai báo bảng nào"
    offenders = [
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if PII_COLUMN_RE.search(column.name)
    ]
    assert not offenders, f"Cột DB giống PII: {offenders}"
