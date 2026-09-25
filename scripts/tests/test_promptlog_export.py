from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

import promptlog_export as pe
import pytest

EMAIL = "nguoi.dung@example.com"
PHONE = "0912345678"
CCCD = "079123456789"
PATTERNS = [
    re.compile(r"(?<!\d)\d{12}(?!\d)"),
    re.compile(r"(?<![\d+])(?:\+84|0)\d{9}(?!\d)"),
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
]


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    root = tmp_path / "docs" / "prompt-log"
    (root / "sessions").mkdir(parents=True)
    body = (
        f'{{"role":"user","content":"email {EMAIL} phone {PHONE} cccd {CCCD} '
        'token hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"}\n'
    )
    session = root / "sessions" / "2026-09-18-abcd1234.jsonl"
    session.write_bytes(body.encode("utf-8"))  # bytes: keep LF on Windows so the hash is stable
    (root / "README.md").write_text("# Prompt log\n", encoding="utf-8")
    (root / "INDEX.md").write_text(
        "# INDEX\n\n| ts | file | sha256 | git_head | status |\n| --- | --- | --- | --- | --- |\n"
        f"| 2026-09-18T00:00:00Z | `sessions/2026-09-18-abcd1234.jsonl` | {pe.sha256_of(session)} "
        "| nogit | closed |\n",
        encoding="utf-8",
    )
    return root


def test_parse_index_supports_subpaths(log_dir: Path) -> None:
    entries = pe.parse_index(log_dir / "INDEX.md")
    assert list(entries) == ["sessions/2026-09-18-abcd1234.jsonl"]


def test_verify_ok_and_unindexed_warning(log_dir: Path) -> None:
    (log_dir / "sessions" / "extra.jsonl").write_text("{}\n", encoding="utf-8")
    problems, warnings = pe.verify(log_dir)
    assert problems == []
    assert warnings and "extra.jsonl" in warnings[0]


def test_verify_detects_tampering_and_missing(log_dir: Path) -> None:
    target = log_dir / "sessions" / "2026-09-18-abcd1234.jsonl"
    target.write_text("edited\n", encoding="utf-8")
    problems, _ = pe.verify(log_dir)
    assert any("KHÔNG khớp" in p for p in problems)
    target.unlink()
    problems, _ = pe.verify(log_dir)
    assert any("không tồn tại" in p for p in problems)


def test_verify_missing_dir_or_index(tmp_path: Path) -> None:
    assert "Thiếu thư mục" in pe.verify(tmp_path / "nope")[0][0]
    (tmp_path / "empty").mkdir()
    assert "Thiếu" in pe.verify(tmp_path / "empty")[0][0]


def test_redact_text_secrets_and_pii() -> None:
    text = f"key=hf_secret123 mail {EMAIL} cccd {CCCD}"
    out, count = pe.redact_text(text, {"hf_secret123"}, PATTERNS)
    assert count == 3
    assert "hf_secret123" not in out and EMAIL not in out and CCCD not in out
    assert out.count("[REDACTED-SECRET sha256:") == 1
    assert out.count("[REDACTED-PII sha256:") == 2
    assert (
        pe.redaction_token("PII", "x")
        == f"[REDACTED-PII sha256:{hashlib.sha256(b'x').hexdigest()[:8]}]"
    )


def test_export_writes_redacted_zip_and_sidecars(log_dir: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    zip_path, digest, records = pe.export(log_dir, out_dir, PATTERNS, use_gitleaks=False)
    assert zip_path.is_file() and len(digest) == 64
    assert (out_dir / "07_PromptLog.zip.sha256").read_text(encoding="utf-8").startswith(digest)
    assert (out_dir / "07_PromptLog.zip.REDACTIONS.md").is_file()
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        assert "prompt-log/REDACTIONS.md" in names and "prompt-log/INDEX.md" in names
        content = archive.read("prompt-log/sessions/2026-09-18-abcd1234.jsonl").decode("utf-8")
    assert EMAIL not in content and PHONE not in content and CCCD not in content
    assert content.count("[REDACTED-PII") == 3
    assert len(records) == 1 and records[0].count == 3
    # originals untouched
    assert pe.verify(log_dir)[0] == []


def test_export_with_gitleaks_secret_injected(
    log_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pe, "gitleaks_secrets", lambda source: ({"hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"}, None)
    )
    zip_path, _, records = pe.export(log_dir, tmp_path / "out", [], use_gitleaks=True)
    with zipfile.ZipFile(zip_path) as archive:
        content = archive.read("prompt-log/sessions/2026-09-18-abcd1234.jsonl").decode("utf-8")
    assert "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in content
    assert "[REDACTED-SECRET sha256:" in content
    assert records[0].count == 1


def test_gitleaks_missing_is_a_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pe.shutil, "which", lambda name: None)
    secrets, warning = pe.gitleaks_secrets(tmp_path)
    assert secrets == set() and warning


def test_main_verify_only_and_export(
    log_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path
    assert pe.main(["--root", str(root), "--verify-only"]) == 0
    assert "hash khớp" in capsys.readouterr().out
    assert pe.main(["--root", str(root), "--no-gitleaks", "--out", str(tmp_path / "o")]) == 0
    assert "Đã đóng gói 1 phiên" in capsys.readouterr().out
    (log_dir / "sessions" / "2026-09-18-abcd1234.jsonl").write_text("x", encoding="utf-8")
    assert pe.main(["--root", str(root), "--verify-only"]) == 1


def test_load_pii_patterns_from_real_config() -> None:
    patterns = pe.load_pii_patterns(pe.REPO_ROOT / "config" / "guardrails.yaml")
    assert len(patterns) >= 5
    assert pe.load_pii_patterns(pe.REPO_ROOT / "nope.yaml") == []
