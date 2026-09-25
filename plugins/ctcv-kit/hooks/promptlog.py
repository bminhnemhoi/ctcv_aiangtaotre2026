"""Prompt-log hook (brief D20): Stop, SessionEnd (``--close``) and ``--sync``.

* Stop: copy ``transcript_path`` to ``docs/prompt-log/sessions/<session_id>.jsonl``
  (idempotent overwrite, INDEX untouched).
* ``--close`` (SessionEnd): copy once more, SHA-256, upsert ONE row per session in
  ``docs/prompt-log/INDEX.md`` (``| ts | file | sha256 | git_head | status |``), index the
  session's subagent transcripts, and write the "system prompt" snapshot
  ``docs/prompt-log/system/<session_id>.json`` (hashes of CLAUDE.md, settings, agents,
  skills, config/prompts + git HEAD).
* ``--sync`` (``make promptlog-sync``): import every transcript from
  ``~/.claude/projects/<slug>/*.jsonl`` that is not yet in INDEX (status ``imported``).

A missing ``transcript_path`` on Stop/SessionEnd exits 1 with a Vietnamese reason
(never silent). The prompt log is competition evidence: nothing here edits a
transcript, only copies and hashes it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from _common import (
    eprint,
    git_head_short,
    now_iso,
    project_dir,
    read_stdin_json,
    safe_id,
    sha256_file,
    utf8_streams,
)

PROMPT_LOG = Path("docs") / "prompt-log"
SESSIONS = "sessions"
SUBAGENTS = "subagents"
SYSTEM = "system"
INDEX_NAME = "INDEX.md"
INDEX_HEADER = "| ts | file | sha256 | git_head | status |"
INDEX_SEPARATOR = "| --- | --- | --- | --- | --- |"
INDEX_PREAMBLE = (
    "# Chỉ mục prompt log\n\n"
    "File này do hook `promptlog` (`.claude/hooks/promptlog.py`) sinh và cập nhật tự động — "
    "**không sửa tay** (BTC nghiêm cấm làm giả prompt log).\n\n"
)
SNAPSHOT_GLOBS = (
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/agents/*.md",
    ".claude/skills/**/SKILL.md",
    "config/prompts/*.md",
)
SLUG_RE = re.compile(r"[^A-Za-z0-9]")
DAY_SECONDS = 86400


# ----------------------------------------------------------------------------- INDEX helpers
def index_path(root: Path) -> Path:
    """Path of ``docs/prompt-log/INDEX.md``."""
    return root / PROMPT_LOG / INDEX_NAME


def _row_cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def indexed_files(root: Path) -> set[str]:
    """Relative file paths (second column) already listed in INDEX.md."""
    path = index_path(root)
    if not path.is_file():
        return set()
    files: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("|"):
            cells = _row_cells(line)
            if len(cells) >= 3 and cells[1] not in ("file", "---", ""):
                files.add(cells[1])
    return files


def upsert_row(root: Path, file_rel: str, sha: str, head: str, status: str, ts: str) -> None:
    """Insert or replace the INDEX row whose ``file`` cell equals ``file_rel``."""
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    lines = text.splitlines()
    if not any(line.strip().startswith("| ts |") for line in lines):
        if lines and lines[-1].strip():
            lines.append("")
        lines = ([INDEX_PREAMBLE.rstrip("\n"), ""] if not lines else lines) + [
            INDEX_HEADER,
            INDEX_SEPARATOR,
        ]
    row = f"| {ts} | {file_rel} | {sha} | {head} | {status} |"
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            cells = _row_cells(line)
            if len(cells) >= 2 and cells[1] == file_rel:
                lines[i] = row
                break
    else:
        lines.append(row)
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- session copy
def session_file(root: Path, session_id: str) -> Path:
    """Destination ``docs/prompt-log/sessions/<session_id>.jsonl``."""
    return root / PROMPT_LOG / SESSIONS / f"{session_id}.jsonl"


def resolve_transcript(data: dict[str, Any]) -> tuple[Path | None, str]:
    """Return ``(transcript path, session_id)``; path is ``None`` when unusable."""
    raw = data.get("transcript_path")
    session_id = safe_id(data.get("session_id") or (Path(raw).stem if isinstance(raw, str) else ""))
    if not isinstance(raw, str) or not raw.strip():
        return None, session_id
    path = Path(raw).expanduser()
    return (path if path.is_file() else None), session_id


def copy_transcript(src: Path, dst: Path) -> None:
    """Copy ``src`` over ``dst`` atomically (temp file + replace)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def snapshot_system(root: Path, session_id: str, head: str, ts: str) -> Path:
    """Write ``system/<session_id>.json`` with SHA-256 of every prompt-shaping file."""
    files: dict[str, str] = {}
    for pattern in SNAPSHOT_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = sha256_file(path)
    out = root / PROMPT_LOG / SYSTEM / f"{session_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"session_id": session_id, "ts": ts, "git_head": head, "files": files}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def do_stop(data: dict[str, Any], root: Path) -> int:
    """Stop: idempotent copy of the transcript, INDEX untouched."""
    src, session_id = resolve_transcript(data)
    if src is None:
        eprint("promptlog: thiếu transcript_path — không ghi được prompt log của phiên này")
        return 1
    copy_transcript(src, session_file(root, session_id))
    return 0


def do_close(data: dict[str, Any], root: Path) -> int:
    """SessionEnd: final copy + hash + one INDEX row per session + system snapshot."""
    src, session_id = resolve_transcript(data)
    if src is None:
        eprint("promptlog --close: thiếu transcript_path — phiên KHÔNG được ghi vào INDEX")
        return 1
    dst = session_file(root, session_id)
    copy_transcript(src, dst)
    ts, head = now_iso(), git_head_short(root)
    log_dir = root / PROMPT_LOG
    upsert_row(root, dst.relative_to(log_dir).as_posix(), sha256_file(dst), head, "closed", ts)
    for extra in sorted((log_dir / SUBAGENTS).glob(f"{session_id}-*.jsonl")):
        upsert_row(
            root, extra.relative_to(log_dir).as_posix(), sha256_file(extra), head, "closed", ts
        )
    snap = snapshot_system(root, session_id, head, ts)
    upsert_row(root, snap.relative_to(log_dir).as_posix(), sha256_file(snap), head, "closed", ts)
    eprint(f"promptlog: đã đóng phiên {session_id} ({dst.relative_to(root).as_posix()})")
    return 0


# ----------------------------------------------------------------------------- sync/import
def project_slugs(cwd: str) -> list[str]:
    """Candidate ``~/.claude/projects`` directory names for ``cwd`` (both drive-letter cases)."""
    variants = {cwd, os.path.abspath(cwd), os.path.normpath(cwd)}
    slugs: list[str] = []
    for variant in variants:
        slug = SLUG_RE.sub("-", variant)
        for candidate in (slug, slug[:1].lower() + slug[1:], slug[:1].upper() + slug[1:]):
            if candidate and candidate not in slugs:
                slugs.append(candidate)
    return slugs


def transcript_dirs(cwd: str) -> list[Path]:
    """Existing ``<config>/projects/<slug>`` directories (``CLAUDE_CONFIG_DIR`` aware)."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(config_dir).expanduser() if config_dir else Path.home() / ".claude"
    projects = base / "projects"
    return [projects / slug for slug in project_slugs(cwd) if (projects / slug).is_dir()]


def sync_transcripts(
    root: Path, cwd: str, max_age_days: float | None = None, skip_ids: set[str] | None = None
) -> list[str]:
    """Import transcripts absent from INDEX; return the imported session ids."""
    known = indexed_files(root)
    skip = skip_ids or set()
    cutoff = time.time() - max_age_days * DAY_SECONDS if max_age_days else None
    imported: list[str] = []
    for directory in transcript_dirs(cwd):
        for src in sorted(directory.glob("*.jsonl")):
            session_id = safe_id(src.stem)
            rel = f"{SESSIONS}/{session_id}.jsonl"
            if session_id in skip or rel in known:
                continue
            if cutoff is not None and src.stat().st_mtime < cutoff:
                continue
            dst = session_file(root, session_id)
            copy_transcript(src, dst)
            upsert_row(root, rel, sha256_file(dst), git_head_short(root), "imported", now_iso())
            known.add(rel)
            imported.append(session_id)
    return imported


def do_sync(root: Path, skip_ids: set[str]) -> int:
    """``make promptlog-sync`` entry: import everything, print a Vietnamese summary."""
    imported = sync_transcripts(root, os.getcwd(), skip_ids=skip_ids)
    if imported:
        print(f"promptlog-sync: đã nhập {len(imported)} phiên: " + ", ".join(imported))
    else:
        print("promptlog-sync: không có phiên mới ngoài INDEX")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI/hook entry point."""
    utf8_streams()
    parser = argparse.ArgumentParser(description="CTCV prompt-log hook")
    parser.add_argument("--close", action="store_true", help="SessionEnd: hash + INDEX + snapshot")
    parser.add_argument("--sync", action="store_true", help="import ~/.claude/projects transcripts")
    parser.add_argument("--skip-session", default=os.environ.get("CLAUDE_SESSION_ID", ""))
    args = parser.parse_args(argv)
    if args.sync:
        skip = {safe_id(args.skip_session)} if args.skip_session else set()
        return do_sync(project_dir(), skip)
    data, error = read_stdin_json()
    if data is None:
        eprint(f"promptlog: không đọc được dữ liệu hook ({error}) — không ghi được prompt log")
        return 1
    root = project_dir(data)
    return do_close(data, root) if args.close else do_stop(data, root)


if __name__ == "__main__":
    sys.exit(main())
