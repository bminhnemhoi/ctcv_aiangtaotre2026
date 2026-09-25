"""Package ``docs/prompt-log`` as ``docs/dossier/out/07_PromptLog.zip`` (brief D12, D20, D21).

Steps:

1. Verify every row of ``docs/prompt-log/INDEX.md``: the file exists and its SHA-256 matches
   (BTC forbids edited prompt logs — originals are never touched by this script).
2. Copy the tree to a temporary directory and run the **redaction gate**: gitleaks (when on
   PATH) plus the PII regexes of ``config/guardrails.yaml``. Every finding is replaced by
   ``[REDACTED-SECRET sha256:<8>]`` or ``[REDACTED-PII sha256:<8>]``.
3. Write ``REDACTIONS.md`` (file, count, hash before/after) inside the archive and next to it.
4. Zip the redacted copy and write a ``.sha256`` sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_LOG_DIR = Path("docs") / "prompt-log"
DEFAULT_OUT_DIR = Path("docs") / "dossier" / "out"
GUARDRAILS_FILE = Path("config") / "guardrails.yaml"
ZIP_NAME = "07_PromptLog.zip"
INDEX_NAME = "INDEX.md"
REDACTIONS_NAME = "REDACTIONS.md"
FILE_CELL_RE = re.compile(r"^[\w][\w./\-]*\.(?:jsonl|json|md|txt)$")
SHA_CELL_RE = re.compile(r"^[a-f0-9]{64}$")
TEXT_SUFFIXES = {".jsonl", ".json", ".md", ".txt", ".yaml", ".yml"}
CHUNK = 1 << 20


@dataclass(frozen=True)
class Redaction:
    """One file that received redactions."""

    file: str
    count: int
    sha_before: str
    sha_after: str


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file, streamed."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def redaction_token(kind: str, secret: str) -> str:
    """``[REDACTED-<KIND> sha256:<8>]`` for a matched string."""
    return f"[REDACTED-{kind} sha256:{hashlib.sha256(secret.encode('utf-8')).hexdigest()[:8]}]"


def parse_index(index_path: Path) -> dict[str, str]:
    """Map ``relative file path → sha256`` from table rows carrying both cells."""
    entries: dict[str, str] = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        files = [c for c in cells if FILE_CELL_RE.match(c) and c != INDEX_NAME]
        hashes = [c for c in cells if SHA_CELL_RE.match(c)]
        if files and hashes:
            entries[files[0]] = hashes[0]
    return entries


def verify(log_dir: Path) -> tuple[list[str], list[str]]:
    """Return ``(problems, warnings)`` for the prompt-log directory."""
    index_path = log_dir / INDEX_NAME
    if not log_dir.is_dir():
        return [f"Thiếu thư mục {log_dir} — prompt log chưa được ghi."], []
    if not index_path.is_file():
        return [f"Thiếu {index_path} — hook promptlog chưa chạy hoặc bị xóa."], []
    entries = parse_index(index_path)
    problems, warnings = [], []
    for name, expected in entries.items():
        path = log_dir / name
        if not path.is_file():
            problems.append(f"INDEX liệt kê {name} nhưng file không tồn tại.")
        elif sha256_of(path) != expected:
            problems.append(f"SHA-256 của {name} KHÔNG khớp INDEX — file đã bị sửa sau khi ghi.")
    for path in sorted(log_dir.rglob("*.jsonl")):
        if path.relative_to(log_dir).as_posix() not in entries:
            warnings.append(
                f"{path.relative_to(log_dir).as_posix()} chưa có trong INDEX.md "
                "(vẫn được đóng gói)."
            )
    return problems, warnings


def load_pii_patterns(guardrails_path: Path) -> list[re.Pattern[str]]:
    """Compile ``pii_patterns`` from config/guardrails.yaml (empty list when missing)."""
    if not guardrails_path.is_file():
        return []
    cfg = yaml.safe_load(guardrails_path.read_text(encoding="utf-8")) or {}
    return [re.compile(item["regex"]) for item in cfg.get("pii_patterns", [])]


def gitleaks_secrets(source: Path) -> tuple[set[str], str | None]:
    """Run gitleaks on ``source``; return ``(secrets, warning)``. Never raises."""
    if shutil.which("gitleaks") is None:
        return set(), "gitleaks không có trên PATH — chỉ che PII bằng regex."
    report = source.parent / "gitleaks-report.json"
    cmd = [
        "gitleaks",
        "detect",
        "--no-git",
        "--source",
        str(source),
        "--report-format",
        "json",
        "--report-path",
        str(report),
        "--exit-code",
        "0",
        "--no-banner",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        findings = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return set(), f"gitleaks lỗi ({exc}) — chỉ che PII bằng regex."
    return {f["Secret"] for f in findings if f.get("Secret")}, None


def redact_text(text: str, secrets: set[str], patterns: list[re.Pattern[str]]) -> tuple[str, int]:
    """Replace secrets (longest first) and PII matches; return ``(text, count)``."""
    count = 0
    for secret in sorted(secrets, key=len, reverse=True):
        occurrences = text.count(secret)
        if occurrences:
            text = text.replace(secret, redaction_token("SECRET", secret))
            count += occurrences

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return redaction_token("PII", match.group(0))

    for pattern in patterns:
        text = pattern.sub(_sub, text)
    return text, count


def redact_tree(
    src: Path, dst: Path, secrets: set[str], patterns: list[re.Pattern[str]]
) -> list[Redaction]:
    """Copy ``src`` into ``dst`` applying redactions to text files; return the records."""
    records: list[Redaction] = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix not in TEXT_SUFFIXES:
            shutil.copy2(path, target)
            continue
        # Bytes in/out so line endings and hashes of untouched files stay identical on Windows.
        text, count = redact_text(
            path.read_bytes().decode("utf-8", errors="replace"), secrets, patterns
        )
        target.write_bytes(text.encode("utf-8"))
        if count:
            records.append(Redaction(rel.as_posix(), count, sha256_of(path), sha256_of(target)))
    return records


def render_redactions(records: list[Redaction], warning: str | None) -> str:
    """Markdown log of what the export redacted (policy D21)."""
    lines = [
        "# Redaction khi xuất prompt log (make promptlog-export)",
        "",
        f"Thời điểm: {datetime.now(UTC).isoformat(timespec='seconds')}. "
        "Bản gốc trong `docs/prompt-log/` không thay đổi; bản xuất thay secret/PII bằng "
        "`[REDACTED-SECRET sha256:<8>]` / `[REDACTED-PII sha256:<8>]` theo chính sách công bố D21.",
        "",
    ]
    if warning:
        lines += [f"Cảnh báo: {warning}", ""]
    if not records:
        lines.append("Không có chuỗi nào cần che.")
        return "\n".join(lines) + "\n"
    lines += [
        "| File | Số chuỗi che | SHA-256 gốc | SHA-256 sau che |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {r.file} | {r.count} | {r.sha_before} | {r.sha_after} |" for r in records]
    return "\n".join(lines) + "\n"


def export(
    log_dir: Path, out_dir: Path, patterns: list[re.Pattern[str]], use_gitleaks: bool = True
) -> tuple[Path, str, list[Redaction]]:
    """Redact into a temp copy, zip it, write the sidecars; return ``(zip, hash, records)``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / ZIP_NAME
    with tempfile.TemporaryDirectory(prefix="ctcv-promptlog-") as tmp:
        staged = Path(tmp) / "prompt-log"
        shutil.copytree(log_dir, staged)
        secrets, warning = (
            gitleaks_secrets(staged)
            if use_gitleaks
            else (set(), "bỏ qua gitleaks (--no-gitleaks).")
        )
        redacted = Path(tmp) / "redacted"
        records = redact_tree(staged, redacted, secrets, patterns)
        (redacted / REDACTIONS_NAME).write_text(
            render_redactions(records, warning), encoding="utf-8"
        )
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(p for p in redacted.rglob("*") if p.is_file()):
                archive.write(path, arcname=str(Path("prompt-log") / path.relative_to(redacted)))
        shutil.copy2(redacted / REDACTIONS_NAME, out_dir / f"{ZIP_NAME}.{REDACTIONS_NAME}")
    digest = sha256_of(zip_path)
    (out_dir / f"{ZIP_NAME}.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="utf-8")
    return zip_path, digest, records


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--out", type=Path, default=None, help="thư mục xuất (mặc định docs/dossier/out)"
    )
    parser.add_argument("--verify-only", action="store_true", help="chỉ kiểm hash, không đóng gói")
    parser.add_argument(
        "--no-gitleaks", action="store_true", help="bỏ bước gitleaks (chỉ regex PII)"
    )
    args = parser.parse_args(argv)
    log_dir = args.root / PROMPT_LOG_DIR
    problems, warnings = verify(log_dir)
    for warning in warnings:
        print(f"CẢNH BÁO: {warning}")
    for problem in problems:
        print(f"LỖI: {problem}")
    if problems:
        return 1
    count = len(parse_index(log_dir / INDEX_NAME))
    if args.verify_only:
        print(f"Prompt log OK: {count} phiên trong INDEX, hash khớp.")
        return 0
    out_dir = args.out if args.out is not None else args.root / DEFAULT_OUT_DIR
    patterns = load_pii_patterns(args.root / GUARDRAILS_FILE)
    zip_path, digest, records = export(
        log_dir, out_dir, patterns, use_gitleaks=not args.no_gitleaks
    )
    redacted = sum(r.count for r in records)
    print(
        f"Đã đóng gói {count} phiên vào {zip_path} (sha256 {digest[:12]}…); "
        f"đã che {redacted} chuỗi trong {len(records)} file."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
