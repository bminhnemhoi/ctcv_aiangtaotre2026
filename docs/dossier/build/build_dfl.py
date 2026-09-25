"""Build the Data for Life 2026 proposal (đề DA940-01, ADR-007) from ``docs/dossier/dfl/``.

    uv run python docs/dossier/build/build_dfl.py --draft   # bản nháp, cho phép team mẫu
    uv run python docs/dossier/build/build_dfl.py              # bản nộp: dừng (mã 1) nếu vi phạm
    uv run python docs/dossier/build/build_dfl.py --no-pdf     # chỉ DOCX (không cần Word)

Steps: fill ``{{eval:…}}`` from ``eval/reports/latest.json`` (+ ``ablation-tthc.json`` under
``ablation``, ``env-tthc.json`` under ``env``), ``{{team_table}}`` and ``{{link:<key>|…}}`` from
the private team file; copy the figures; render DOCX and PDF with ``md_to_pdf.convert`` (the H1
is kept as a centred title unless the source already opens with a bold title line); check
≤ 10 pages, ≤ 10 MB, no markers left and the form character limits of ``mo-ta-ngan.md``; write
``build-report.json``. Numbers are never invented: a missing report leaves the placeholder
fallback ("chưa đo").
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_dossier as bd  # noqa: E402
import md_to_pdf  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DFL_DIR = REPO_ROOT / "docs" / "dossier" / "dfl"
OUT_DIR = REPO_ROOT / "docs" / "dossier" / "out" / "dfl"
TEAM_PATH = REPO_ROOT / "docs" / "dossier" / "private" / "team-dfl.yaml"
EVAL_PATH = REPO_ROOT / "eval" / "reports" / "latest.json"
ABLATION_PATH = REPO_ROOT / "eval" / "reports" / "ablation-tthc.json"
ENV_NAME = "env-tthc.json"  # machine/model record of the eval run, next to latest.json

PROPOSAL_MD = "de-xuat-giai-phap.md"
SHORT_MD = "mo-ta-ngan.md"
SHORT_FILLED = "mo-ta-ngan.filled.md"
COMMITMENT_MD = "cam-ket.md"
TEAM_EXAMPLE_NAME = "team-dfl.example.yaml"
REPORT_NAME = "build-report.json"

# Data for Life 2026 limits (docs/competition/DFL-2026-yeu-cau.md §1.5).
MAX_PAGES = 10
MAX_BYTES = 10 * 1024 * 1024
LIMIT_NAME = 400
LIMIT_DESCRIPTION = 2000
LIMIT_TEAM_BOX = 2000
LIMIT_MEMBER = 500

LINK_RE = re.compile(r"\{\{link:([\w.\-]+)(?:\|([^{}]*))?\}\}")
TEAM_TABLE = "{{team_table}}"
MARKER_RE = re.compile(r"\{\{[^{}]*\}\}|⟪[^⟫]*⟫")
IMAGE_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)\)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.MULTILINE)
PAGES_TYPE_RE = re.compile(rb"/Type\s*/Pages(?![A-Za-z0-9])")
PAGE_TYPE_RE = re.compile(rb"/Type\s*/Page(?![A-Za-z0-9])")
COUNT_RE = re.compile(rb"/Count\s+(\d+)(?!\s+\d+\s+R)")
STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
BOLD_LINE_RE = re.compile(r"^\*\*[^*]+\*\*$")
SLUG_RE = re.compile(r"[^a-z0-9]+")
TITLE_H1 = "h1"
TITLE_BOLD = "in_dam_co_san"
TITLE_NONE = "khong_co"


class DflBuildError(Exception):
    """A build input is missing or invalid (message in Vietnamese)."""


@dataclass(frozen=True)
class BuildOptions:
    """Inputs and switches of one build."""

    draft: bool = False
    pdf: bool = True
    src_dir: Path = DFL_DIR
    out_dir: Path = OUT_DIR
    team_path: Path = TEAM_PATH
    team_example_path: Path = DFL_DIR / TEAM_EXAMPLE_NAME
    eval_path: Path = EVAL_PATH
    ablation_path: Path = ABLATION_PATH
    env_path: Path | None = None  # None → ``env-tthc.json`` next to ``eval_path``


# ------------------------------------------------------------------ inputs


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DflBuildError(f"{path}: JSON không hợp lệ ({exc}).") from exc
    if not isinstance(value, dict):
        raise DflBuildError(f"{path}: cần một object JSON ở gốc.")
    return value


def _merge_optional(
    data: dict[str, Any], key: str, path: Path, warnings: list[str]
) -> dict[str, Any] | None:
    if not path.is_file():
        warnings.append(f"Chưa có {path.name}: mọi {{{{eval:{key}.…}}}} giữ giá trị dự phòng.")
        return None
    data[key] = _read_object(path)
    return data[key]


def _slug(tag: str) -> str:
    return SLUG_RE.sub("_", tag.lower()).strip("_")


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    return value if isinstance(value, dict) else {}


def add_env_aliases(run_env: dict[str, Any]) -> None:
    """Add short keys copied from the raw env report (never computed, never guessed).

    ``cpu``/``cpu_count``/``ram_gb``/``gpu`` come from ``machine``, ``commit``/``code_sha256``
    from ``code``, and ``model.<slug>`` merges an Ollama model entry with its
    ``loaded_at_end_of_run`` entry (``qwen3.5:2b`` → ``model.qwen3_5_2b.quantization``).
    """
    machine, code = _mapping(run_env, "machine"), _mapping(run_env, "code")
    adapters = machine.get("gpu_adapters")
    aliases = {
        "cpu": machine.get("cpu"),
        "cpu_count": machine.get("logical_cores"),
        "ram_gb": machine.get("ram_gb"),
        "gpu": ", ".join(map(str, adapters)) if isinstance(adapters, list) and adapters else None,
        "commit": code.get("commit"),
        "code_sha256": code.get("sha256"),
    }
    for key, value in aliases.items():
        if value is not None:
            run_env.setdefault(key, value)
    ollama = _mapping(run_env, "ollama")
    models: dict[str, dict[str, Any]] = {}
    for entry in _dicts(ollama.get("models")) + _dicts(ollama.get("loaded_at_end_of_run")):
        if entry.get("tag"):
            models.setdefault(_slug(str(entry["tag"])), {}).update(entry)
    if models:
        run_env.setdefault("model", models)


def load_data(
    eval_path: Path, ablation_path: Path, warnings: list[str], env_path: Path | None = None
) -> dict[str, Any]:
    """Return the eval report with the ablation and run-environment reports merged in.

    ``ablation-tthc.json`` goes under ``ablation`` and ``env-tthc.json`` (default: next to
    ``eval_path``) under ``env``, with the short aliases of :func:`add_env_aliases`.
    """
    try:
        data = bd.load_eval_report(eval_path, warnings)
    except bd.DossierError as exc:
        raise DflBuildError(str(exc)) from exc
    _merge_optional(data, "ablation", ablation_path, warnings)
    run_env = _merge_optional(data, "env", env_path or eval_path.with_name(ENV_NAME), warnings)
    if run_env is not None:
        add_env_aliases(run_env)
    return data


def load_team(team_path: Path, example_path: Path, *, draft: bool) -> tuple[dict[str, Any], bool]:
    """Return the team data and whether the example file had to be used (draft only)."""
    if team_path.is_file():
        return bd.load_yaml(team_path), False
    if not draft:
        raise DflBuildError(
            f"Thiếu {team_path} (thông tin đội, gitignore). Chép từ {example_path.name} và "
            "điền thông tin thật, hoặc chạy với --draft."
        )
    if not example_path.is_file():
        raise DflBuildError(f"Thiếu cả {team_path.name} lẫn {example_path}.")
    return bd.load_yaml(example_path), True


# ------------------------------------------------------------------ placeholders


def _cell(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text.replace("|", "\\|") if text else "—"


def team_table(team: dict[str, Any]) -> str:
    """Render ``members`` as a Markdown table: Họ tên | Vai trò | Trình độ | Năng lực."""
    members = [m for m in team.get("members") or [] if isinstance(m, dict)]
    if not members:
        return "⟪CHƯA CÓ: team.members⟫"
    rows = ["| Họ tên | Vai trò | Trình độ | Năng lực |", "| --- | --- | --- | --- |"]
    for member in members:
        cells = (member.get(k) for k in ("ho_ten", "vai_tro", "trinh_do", "nang_luc"))
        rows.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(rows)


def _link_repl(team: dict[str, Any]) -> Callable[[re.Match[str]], str]:
    links = team.get("lien_ket") if isinstance(team.get("lien_ket"), dict) else {}

    def repl(match: re.Match[str]) -> str:
        value = links.get(match.group(1))
        if not bd.is_placeholder(value):
            return str(value).strip()
        fallback = (match.group(2) or "").strip()
        return fallback or f"⟪CHƯA CÓ: link.{match.group(1)}⟫"

    return repl


def fill(text: str, data: dict[str, Any], team: dict[str, Any]) -> str:
    """Replace ``{{team_table}}``, ``{{link:…}}``, ``{{eval:…}}`` and ``{{team:…}}``."""
    text = text.replace(TEAM_TABLE, team_table(team))
    text = LINK_RE.sub(_link_repl(team), text)
    return bd.substitute(text, data, team)


def title_source(markdown: str) -> str:
    """How the proposal carries its title: kept ``h1``, a hand-made bold line, or none.

    A bold-only line right after the H1 is an explicit title block written in the source;
    rendering the H1 as well would print the title twice, so the H1 is then dropped.
    """
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("# "):
        return TITLE_NONE
    if len(lines) > 1 and BOLD_LINE_RE.match(lines[1]):
        return TITLE_BOLD
    return TITLE_H1


def markers_left(text: str) -> list[str]:
    """Distinct ``{{…}}`` placeholders and ``⟪…⟫`` markers, in order of appearance."""
    seen: dict[str, None] = {}
    for match in MARKER_RE.finditer(text):
        seen.setdefault(match.group(0), None)
    return list(seen)


def resolve_images(text: str, base_dir: Path, *, draft: bool) -> tuple[str, list[str]]:
    """Replace images missing under ``base_dir`` by ``⟪THIẾU ẢNH: tên⟫`` (draft) or fail."""
    missing: list[str] = []

    def repl(match: re.Match[str]) -> str:
        path = match.group("path")
        if (base_dir / path).is_file():
            return match.group(0)
        missing.append(path)
        return f"⟪THIẾU ẢNH: {Path(path).name}⟫"

    out = IMAGE_RE.sub(repl, text)
    if missing and not draft:
        raise DflBuildError(
            "Thiếu ảnh: " + ", ".join(missing) + " (chạy figures.demo.ts / record-demo.demo.ts)."
        )
    return out, missing


# ------------------------------------------------------------------ PDF pages


def _dict_around(data: bytes, pos: int) -> bytes:
    """Return the ``<< … >>`` dictionary that contains ``pos`` (best effort)."""
    depth, start = 0, pos
    while start > 0:
        start -= 1
        if data.startswith(b">>", start):
            depth += 1
        elif data.startswith(b"<<", start):
            if depth == 0:
                break
            depth -= 1
    depth, end = 0, start
    while end < len(data):
        if data.startswith(b"<<", end):
            depth += 1
            end += 2
            continue
        if data.startswith(b">>", end):
            depth -= 1
            end += 2
            if depth == 0:
                break
            continue
        end += 1
    return data[start:end]


def _inflated_streams(data: bytes) -> bytes:
    parts: list[bytes] = []
    for match in STREAM_RE.finditer(data):
        try:
            parts.append(zlib.decompress(match.group(1)))
        except zlib.error:
            continue
    return b"\n".join(parts)


def count_pdf_pages(data: bytes) -> int | None:
    """Largest ``/Count`` of a ``/Type /Pages`` node, else the number of ``/Type /Page``."""
    haystack = data + b"\n" + _inflated_streams(data)
    counts = [
        int(found.group(1))
        for match in PAGES_TYPE_RE.finditer(haystack)
        if (found := COUNT_RE.search(_dict_around(haystack, match.start())))
    ]
    if counts:
        return max(counts)
    pages = len(PAGE_TYPE_RE.findall(haystack))
    return pages or None


def limit_violations(*, pages: int | None, size: int | None, pdf_expected: bool) -> list[str]:
    """Check the page and size limits of the PDF proposal."""
    if not pdf_expected:
        return []
    if size is None:
        return ["Chưa xuất được PDF (cần Microsoft Word hoặc LibreOffice)."]
    problems: list[str] = []
    if pages is None:
        problems.append("Số trang PDF: không đếm được.")
    elif pages > MAX_PAGES:
        problems.append(f"PDF có {pages} trang, vượt giới hạn {MAX_PAGES} trang.")
    if size > MAX_BYTES:
        problems.append(f"PDF nặng {size:,} byte, vượt giới hạn 10 MB.".replace(",", "."))
    return problems


# ------------------------------------------------------------------ form limits


def _sections(text: str) -> list[tuple[int, str, str]]:
    """Split Markdown into ``(level, title, body)`` for ``##`` and ``###`` headings."""
    text = unicodedata.normalize("NFC", text)
    heads = list(HEADING_RE.finditer(text))
    out: list[tuple[int, str, str]] = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((len(head.group(1)), head.group(2), text[head.end() : end].strip()))
    return out


def form_fields(text: str) -> dict[str, tuple[str, int]]:
    """Map each form box of ``mo-ta-ngan.md`` to ``(text, limit)``."""
    fields: dict[str, tuple[str, int]] = {}
    parent = ""
    for level, title, body in _sections(text):
        if level == 2:
            parent = title
            if title == "Tên giải pháp":
                fields["ten_giai_phap"] = (body, LIMIT_NAME)
            elif title == "Mô tả ngắn":
                fields["mo_ta_ngan"] = (body, LIMIT_DESCRIPTION)
        elif parent == "Năng lực đội":
            fields[f"nang_luc:{title}"] = (body, LIMIT_TEAM_BOX)
        elif parent == "Tóm tắt kinh nghiệm từng thành viên":
            fields[f"thanh_vien:{title}"] = (body, LIMIT_MEMBER)
    return fields


def _count(chars: int | None, limit: int) -> dict[str, Any]:
    return {"chars": chars, "limit": limit, "ok": chars is not None and chars <= limit}


def char_counts(text: str, team: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Character counts of every form box (missing required boxes → ``chars: None``)."""
    fields = form_fields(text)
    counts = {key: _count(len(body), limit) for key, (body, limit) in fields.items()}
    counts.setdefault("ten_giai_phap", _count(None, LIMIT_NAME))
    counts.setdefault("mo_ta_ngan", _count(None, LIMIT_DESCRIPTION))
    for i, member in enumerate(team.get("members") or []):
        if isinstance(member, dict) and member.get("nang_luc") is not None:
            summary = unicodedata.normalize("NFC", str(member["nang_luc"]).strip())
            counts[f"team.members[{i}].nang_luc"] = _count(len(summary), LIMIT_MEMBER)
    return counts


# ------------------------------------------------------------------ build


def _copy_figures(src_dir: Path, out_dir: Path) -> None:
    figures = src_dir / "figures"
    if figures.is_dir():
        shutil.copytree(
            figures, out_dir / "figures", dirs_exist_ok=True, ignore=shutil.ignore_patterns("src")
        )


def _render_pdf(
    md_path: Path, out_dir: Path, *, pdf: bool, keep_title: bool = False
) -> tuple[Path, Path | None]:
    try:
        return md_to_pdf.convert(md_path, out_dir, pdf=pdf, keep_title=keep_title)
    except Exception as exc:  # noqa: BLE001 - Word/LibreOffice failures become a violation
        raise DflBuildError(f"Không dựng được {md_path.name}: {exc}") from exc


def _write_short(
    opts: BuildOptions, data: dict[str, Any], team: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    text = fill((opts.src_dir / SHORT_MD).read_text(encoding="utf-8"), data, team)
    (opts.out_dir / SHORT_FILLED).write_text(text, encoding="utf-8")
    boxes = "\n".join(body for body, _ in form_fields(text).values())
    return char_counts(text, team), markers_left(boxes)


def _violations(report: dict[str, Any], pdf_expected: bool) -> list[str]:
    problems = limit_violations(
        pages=report["pages"], size=report["bytes"], pdf_expected=pdf_expected
    )
    problems += [f"Còn placeholder/marker: {m}" for m in report["markers_left"]]
    problems += [
        f"Ô '{key}' dài {item['chars']} ký tự, giới hạn {item['limit']}."
        if item["chars"] is not None
        else f"Thiếu mục '{key}' trong {SHORT_MD}."
        for key, item in report["char_counts"].items()
        if not item["ok"]
    ]
    return problems


def build(opts: BuildOptions) -> dict[str, Any]:
    """Run the build and write ``build-report.json``; return the report."""
    warnings: list[str] = []
    data = load_data(opts.eval_path, opts.ablation_path, warnings, opts.env_path)
    team, used_example = load_team(opts.team_path, opts.team_example_path, draft=opts.draft)
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    _copy_figures(opts.src_dir, opts.out_dir)
    proposal = fill((opts.src_dir / PROPOSAL_MD).read_text(encoding="utf-8"), data, team)
    proposal, missing = resolve_images(proposal, opts.out_dir, draft=opts.draft)
    proposal_md = opts.out_dir / PROPOSAL_MD
    proposal_md.write_text(proposal, encoding="utf-8")
    counts, short_markers = _write_short(opts, data, team)
    commitment = opts.out_dir / COMMITMENT_MD
    commitment.write_text(
        (opts.src_dir / COMMITMENT_MD).read_text(encoding="utf-8"), encoding="utf-8"
    )
    _render_pdf(commitment, opts.out_dir, pdf=False)
    title = title_source(proposal)
    docx, pdf = _render_pdf(proposal_md, opts.out_dir, pdf=opts.pdf, keep_title=title == TITLE_H1)
    pdf_bytes = pdf.read_bytes() if pdf and pdf.is_file() else None
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "draft": opts.draft,
        "pdf": str(pdf) if pdf_bytes is not None else None,
        "docx": str(docx),
        "pages": count_pdf_pages(pdf_bytes) if pdf_bytes is not None else None,
        "title": title,
        "bytes": len(pdf_bytes) if pdf_bytes is not None else None,
        "markers_left": markers_left(proposal + "\n" + "\n".join(short_markers)),
        "missing_images": missing,
        "char_counts": counts,
        "used_example_team": used_example,
        "warnings": warnings,
    }
    report["violations"] = _violations(report, opts.pdf)
    report["ok"] = not report["violations"]
    (opts.out_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


# ------------------------------------------------------------------ CLI


def parse_args(argv: list[str] | None = None) -> BuildOptions:
    """Parse the command line into :class:`BuildOptions`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--draft", action="store_true", help="bản nháp (cho phép marker)")
    parser.add_argument("--no-pdf", action="store_true", help="chỉ DOCX, không gọi Word")
    parser.add_argument("--src", type=Path, default=DFL_DIR)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--team", type=Path, default=TEAM_PATH)
    parser.add_argument("--eval", type=Path, default=EVAL_PATH)
    parser.add_argument("--ablation", type=Path, default=ABLATION_PATH)
    parser.add_argument("--env", type=Path, default=None, help=f"mặc định: {ENV_NAME} cạnh --eval")
    args = parser.parse_args(argv)
    return BuildOptions(
        draft=args.draft,
        pdf=not args.no_pdf,
        src_dir=args.src,
        out_dir=args.out,
        team_path=args.team,
        team_example_path=args.src / TEAM_EXAMPLE_NAME,
        eval_path=args.eval,
        ablation_path=args.ablation,
        env_path=args.env,
    )


def print_report(report: dict[str, Any]) -> None:
    """Print a short human summary (Vietnamese)."""
    print(f"PDF:   {report['pdf'] or 'chưa có'}")
    pages = report["pages"] if report["pages"] is not None else "không đếm được / chưa có"
    print(f"Trang: {pages} (tối đa {MAX_PAGES}) · Dung lượng: {report['bytes'] or '—'} byte")
    for key, item in report["char_counts"].items():
        mark = "ok " if item["ok"] else "LỖI"
        print(f"  [{mark}] {key}: {item['chars']}/{item['limit']} ký tự")
    for warning in report["warnings"]:
        print(f"Cảnh báo: {warning}")
    label = "Ghi chú (bản nháp)" if report["draft"] else "VI PHẠM"
    for problem in report["violations"]:
        print(f"{label}: {problem}")
    print("Kết quả: " + ("đạt" if report["ok"] else "chưa đạt"))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: exit 1 on errors, or on violations when not ``--draft``."""
    bd._utf8_stdout()
    opts = parse_args(argv)
    try:
        report = build(opts)
    except DflBuildError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    print_report(report)
    return 0 if opts.draft or report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
