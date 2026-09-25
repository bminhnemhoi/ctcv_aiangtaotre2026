"""Generate the BTC AI declaration (``docs/dossier/out/06_KeKhaiAI.md``).

Sources: ``data/registry/datasets.yaml``, ``data/registry/models.yaml``, ``uv.lock``,
``apps/web/package.json`` and ``docs/prompt-log/INDEX.md``. Missing inputs are
tolerated and reported so the draft can be produced from day one; ``config/models.yaml``
is the fallback list of base models until the registry exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path("docs") / "dossier" / "out" / "06_KeKhaiAI.md"
INDEX_ROW_RE = re.compile(r"\b[a-f0-9]{64}\b")

# Modules the team writes itself (brief §1) — listed when the directory exists.
TEAM_MODULES: tuple[tuple[str, str], ...] = (
    ("apps/web", "PWA React chữ to, giọng nói, 3 vai"),
    ("apps/android", "Ghi chú hướng phát triển bản offline (chưa có mã; APK hoãn sau cuộc thi)"),
    ("services/api", "API FastAPI: auth, lớp học, phiên sandbox, báo cáo"),
    ("services/agent", "Planner, LLM cách ly, tool router, guardrails, kiểm chứng trích dẫn"),
    (
        "services/speech",
        "Dịch vụ giọng nói: khung API ASR/TTS, khóa cache TTS (tích hợp mô hình ở E04)",
    ),
    (
        "services/vision",
        "Dịch vụ đọc ảnh màn hình sandbox: khung API, che vùng nhạy cảm, TTL ảnh 60 s (VLM ở E08)",
    ),
    ("sandbox", "Máy trạng thái sandbox, validator, kịch bản JSON (lộ trình 12 kịch bản × 3 mức)"),
    ("drills", "Vắc-xin lừa đảo: kịch bản mức dấu hiệu, chấm điểm"),
    ("data", "Pipeline crawl → chuẩn hóa → sinh → lọc → registry"),
    (
        "training",
        "Cấu hình LoRA SFT/DPO, lượng tử hóa, ngân sách GPU, thẻ mô hình (huấn luyện ở Pha D)",
    ),
    ("eval", "Bộ đánh giá 6 suite, red-team, load test"),
    ("deploy", "Docker Compose, Caddy, giám sát, backup, failover"),
    ("libs/core", "Thư viện dùng chung: config, lỗi, log không PII"),
)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def load_registry(root: Path, name: str, notes: list[str]) -> list[dict[str, Any]]:
    """Load ``data/registry/<name>.yaml`` as a list; report when missing or malformed."""
    path = root / "data" / "registry" / f"{name}.yaml"
    if not path.is_file():
        notes.append(f"Thiếu {path.relative_to(root)} — bảng {name} để trống (WP H / make data).")
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        notes.append(f"{path.relative_to(root)} không phải danh sách — bỏ qua.")
        return []
    return [row for row in data if isinstance(row, dict)]


def base_models_from_config(root: Path) -> list[dict[str, Any]]:
    """Fallback rows from config/models.yaml (always present)."""
    path = root / "config" / "models.yaml"
    if not path.is_file():
        return []
    models = yaml.safe_load(path.read_text(encoding="utf-8")).get("models", {})
    return [
        {
            "name": key,
            "base": m.get("id", "?"),
            "license": m.get("license", "?"),
            "role": m.get("kind", ""),
        }
        for key, m in models.items()
    ]


def load_uv_lock(root: Path, notes: list[str]) -> list[dict[str, str]]:
    """Third-party Python packages from uv.lock (workspace members excluded)."""
    path = root / "uv.lock"
    if not path.is_file():
        notes.append("Thiếu uv.lock — chạy `uv lock`.")
        return []
    packages = tomllib.loads(path.read_text(encoding="utf-8")).get("package", [])
    rows = []
    for pkg in packages:
        source = pkg.get("source", {})
        if "editable" in source or "virtual" in source:
            continue
        origin = "PyPI" if "registry" in source else next(iter(source), "?")
        rows.append(
            {"name": pkg.get("name", "?"), "version": pkg.get("version", "?"), "source": origin}
        )
    return sorted(rows, key=lambda r: r["name"])


def load_web_deps(root: Path, notes: list[str]) -> list[dict[str, str]]:
    """Dependencies declared by apps/web/package.json (missing → empty)."""
    path = root / "apps" / "web" / "package.json"
    if not path.is_file():
        notes.append("Chưa có apps/web/package.json — bảng thư viện web để trống (WP G).")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for section in ("dependencies", "devDependencies"):
        for name, version in sorted(data.get(section, {}).items()):
            rows.append({"name": name, "version": str(version), "section": section})
    return rows


def count_prompt_log_sessions(root: Path) -> int:
    """Number of hashed sessions in docs/prompt-log/INDEX.md."""
    path = root / "docs" / "prompt-log" / "INDEX.md"
    if not path.is_file():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if INDEX_ROW_RE.search(line)
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(chưa có mục nào)_\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def render(
    root: Path,
    models: list[dict],
    datasets: list[dict],
    py: list[dict],
    web: list[dict],
    sessions: int,
) -> str:
    """Render the declaration markdown."""
    modules = [[p, d] for p, d in TEAM_MODULES if (root / p).is_dir()]
    tuned = [
        [m["name"], m.get("base", "?"), m.get("quantization", "?"), m.get("adapter_path") or "—"]
        for m in models
        if m.get("adapter_path")
    ]
    synthetic = [
        [d["name"], d.get("version", ""), ", ".join(d.get("used_for", [])), d.get("license", "")]
        for d in datasets
        if d.get("source") == "synthetic"
    ]
    external = [
        [d["name"], d.get("source", ""), d.get("license", ""), ", ".join(d.get("used_for", []))]
        for d in datasets
        if d.get("source") != "synthetic"
    ]
    bases = [
        [m["name"], m.get("base", "?"), m.get("license", "?")]
        for m in (models or base_models_from_config(root))
    ]
    parts = [
        "# Bản kê khai công cụ AI, bộ dữ liệu, API, thư viện, mã nguồn mở "
        "và phần việc do đội tự xây dựng\n",
        "Sản phẩm: **Cầm Tay Chỉ Việc (CTCV)** · Sinh tự động bởi `scripts/declaration.py` "
        f"ngày {date.today().isoformat()} từ registry, `uv.lock`, `package.json` và "
        "`docs/prompt-log/INDEX.md`. Không chỉnh tay; sửa nguồn rồi chạy `make declaration`.\n",
        "## 1. Đội tự xây\n",
        "### 1.1 Mã nguồn\n",
        _table(["Thư mục", "Nội dung"], modules),
        "### 1.2 Mô hình đội fine-tune / lượng tử hóa\n",
        _table(["Tên", "Mô hình gốc", "Lượng tử hóa", "Adapter"], tuned),
        "### 1.3 Dữ liệu đội tự sinh (CC BY 4.0)\n",
        _table(["Tên", "Phiên bản", "Dùng cho", "Giấy phép"], synthetic),
        "## 2. AI hỗ trợ\n",
        _table(
            ["Công cụ", "Nhà cung cấp", "Dùng để", "Minh chứng"],
            [
                [
                    "Claude Code",
                    "Anthropic",
                    (
                        "Viết mã, test, tài liệu theo prompt và quyết định thiết kế của đội "
                        "(mô hình "
                        "Claude Fable 5.1)"
                    ),
                    f"{sessions} phiên có hash trong docs/prompt-log/INDEX.md (07_PromptLog.zip)",
                ],
                [
                    "Mô hình sinh dữ liệu tổng hợp và LLM-judge",
                    (
                        "Ưu tiên mô hình mở cho phép dùng đầu ra (Qwen3.5 tự host); "
                        "nếu dùng API ngoài "
                        "thì kê khai tên, giấy phép, ngày kiểm tra điều khoản"
                    ),
                    (
                        "Chỉ bước sinh hội thoại tổng hợp (E06) và chấm offline; "
                        "không chạy trong sản "
                        "phẩm; chưa dùng khi registry chưa có tập synthetic"
                    ),
                    (
                        "data/registry/datasets.yaml (generator_model, tos_checked_on); "
                        "docs/prompt-log/tools/"
                    ),
                ],
            ],
        ),
        "## 3. Kế thừa mã nguồn mở\n",
        "### 3.1 Mô hình gốc\n",
        _table(["Vai trò", "Mô hình", "Giấy phép"], bases),
        "### 3.2 Bộ dữ liệu bên ngoài\n",
        _table(["Tên", "Nguồn", "Giấy phép", "Dùng cho"], external),
        "### 3.3 Thư viện Python (uv.lock)\n",
        _table(["Gói", "Phiên bản", "Nguồn"], [[p["name"], p["version"], p["source"]] for p in py]),
        "### 3.4 Thư viện web (apps/web/package.json)\n",
        _table(
            ["Gói", "Phiên bản", "Nhóm"], [[w["name"], w["version"], w["section"]] for w in web]
        ),
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    notes: list[str] = []
    models = load_registry(args.root, "models", notes)
    datasets = load_registry(args.root, "datasets", notes)
    text = render(
        args.root,
        models,
        datasets,
        load_uv_lock(args.root, notes),
        load_web_deps(args.root, notes),
        count_prompt_log_sessions(args.root),
    )
    out = args.out if args.out is not None else args.root / DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    for note in notes:
        print(f"LƯU Ý: {note}")
    print(f"Đã ghi bản kê khai vào {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
