"""Dataset/model registry: validate ``data/registry/*.yaml``, hash artefacts, write REPORT.md.

Schemas live in ``config/schemas/{datasets,models}-registry.schema.json`` (brief §9, §17.4).
An entry whose ``path`` exists on disk gets its SHA-256 computed; ``sha256: pending`` is a
warning, a declared hash that differs from the computed one is an error. The AI declaration
(``scripts/declaration.py``) reads the same files, so they must stay valid at all times.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ctcv_core.config import ConfigError, schema_path, validate_against_schema
from ctcv_core.paths import REPO_ROOT

REGISTRY_DIRNAME = "registry"
REPORT_NAME = "REPORT.md"
REGISTRY_SCHEMAS: dict[str, str] = {"datasets": "datasets-registry", "models": "models-registry"}
PENDING = "pending"
_NC_LICENSE_RE = re.compile(r"BY-NC|NonCommercial|Non-Commercial", re.IGNORECASE)
_CHUNK = 1 << 20


@dataclass(slots=True)
class HashCheck:
    """Outcome of comparing a dataset entry's declared hash with the artefact on disk."""

    name: str
    path: str | None
    exists: bool
    declared: str
    computed: str | None
    status: str  # match | mismatch | pending | missing | no_path


@dataclass(slots=True)
class RegistryResult:
    """Everything the registry step reports."""

    ok: bool
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hash_checks: list[HashCheck] = field(default_factory=list)
    datasets: list[dict[str, Any]] = field(default_factory=list)
    models: list[dict[str, Any]] = field(default_factory=list)
    report_path: Path | None = None


def registry_dir(root: Path | None = None) -> Path:
    """``<root>/data/registry``."""
    return (root or REPO_ROOT) / "data" / REGISTRY_DIRNAME


def _dates_to_str(value: Any) -> Any:
    """YAML parses ``2026-09-18`` as ``date``; JSON Schema wants ISO strings."""
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _dates_to_str(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dates_to_str(v) for v in value]
    return value


def load_registry(name: str, directory: Path) -> list[dict[str, Any]]:
    """Read ``<directory>/<name>.yaml`` as a list of mappings (dates normalised to strings)."""
    path = directory / f"{name}.yaml"
    if not path.is_file():
        raise ConfigError(f"Thiếu registry {path}", {"path": str(path)})
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    if not isinstance(data, list):
        raise ConfigError(f"{path.name} phải là một danh sách các mục.", {"path": str(path)})
    return [_dates_to_str(item) for item in data]


def _load_schema(name: str, root: Path) -> dict[str, Any]:
    import json

    return json.loads(schema_path(REGISTRY_SCHEMAS[name], root).read_text(encoding="utf-8"))


def validate_entries(name: str, entries: list[dict[str, Any]], root: Path) -> list[str]:
    """Schema-validate ``entries`` and apply the cross-entry rules; return problems (vi).

    Schema errors and cross-entry problems (duplicate names, dangling ``derived_from``,
    NC-license rules) are collected together so one run reports everything at once.
    """
    problems: list[str] = []
    try:
        validate_against_schema(entries, _load_schema(name, root), f"{name}.yaml")
    except ConfigError as exc:
        errors = (exc.details or {}).get("errors") or [exc.message_vi]
        problems.extend(f"{name}.yaml: {err}" for err in errors)
    mappings = [e for e in entries if isinstance(e, dict)]
    names = [str(e.get("name")) for e in mappings]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f"{name}.yaml: tên trùng '{dup}'")
    if name == "datasets":
        problems.extend(_dataset_rules(mappings, set(names)))
    return problems


def _dataset_rules(entries: list[dict[str, Any]], names: set[str]) -> list[str]:
    problems: list[str] = []
    for entry in entries:
        label = f"datasets.yaml[{entry.get('name')}]"
        for parent in entry.get("derived_from", []):
            if parent not in names:
                problems.append(f"{label}: derived_from trỏ tới '{parent}' không có trong registry")
        if _NC_LICENSE_RE.search(str(entry.get("license", ""))):
            if entry.get("eval_only") is not True or entry.get("redistribute") is not False:
                problems.append(
                    f"{label}: giấy phép NC phải có eval_only: true và redistribute: false"
                )
        if entry.get("eval_only") and entry.get("used_for") != ["eval"]:
            problems.append(f"{label}: eval_only nhưng used_for khác ['eval']")
    return problems


def sha256_of_path(path: Path) -> str:
    """SHA-256 of a file, or of a directory (sorted relative paths + per-file hashes)."""
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file.relative_to(path).as_posix()
        digest.update(f"{rel}\n{sha256_of_path(file)}\n".encode())
    return digest.hexdigest()


def check_hashes(entries: list[dict[str, Any]], root: Path) -> list[HashCheck]:
    """Compute the hash of every dataset whose ``path`` exists and compare with ``sha256``."""
    checks: list[HashCheck] = []
    for entry in entries:
        name, declared = str(entry.get("name")), str(entry.get("sha256", PENDING))
        rel = entry.get("path")
        if not rel:
            checks.append(HashCheck(name, None, False, declared, None, "no_path"))
            continue
        target = root / rel
        if not target.exists():
            checks.append(HashCheck(name, rel, False, declared, None, "missing"))
            continue
        computed = sha256_of_path(target)
        if declared == PENDING:
            status = PENDING
        else:
            status = "match" if computed == declared else "mismatch"
        checks.append(HashCheck(name, rel, True, declared, computed, status))
    return checks


def update_sha256(path: Path, name: str, new_hash: str) -> bool:
    """Rewrite ``sha256:`` of entry ``name`` inside the YAML text, keeping comments intact."""
    text = path.read_text(encoding="utf-8")
    block = re.compile(
        rf"(^-\s+name:\s*{re.escape(name)}\s*$.*?)(^\s+sha256:\s*)(\S+)(\s*$)",
        re.MULTILINE | re.DOTALL,
    )
    match = block.search(text)
    if match is None or match.group(3) == new_hash:
        return False
    text = text[: match.start(3)] + new_hash + text[match.end(3) :]
    path.write_text(text, encoding="utf-8")
    return True


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(chưa có mục nào)_\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def render_report(result: RegistryResult, now: dt.datetime | None = None) -> str:
    """Markdown report (Vietnamese) summarising the registry and its hash checks."""
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    hashes = {h.name: h for h in result.hash_checks}
    dataset_rows = [
        [
            d["name"],
            d["version"],
            d["source_type"],
            d["license"],
            "có" if d["redistribute"] else "không",
            ", ".join(d["used_for"]),
            hashes[d["name"]].status if d["name"] in hashes else "—",
        ]
        for d in result.datasets
    ]
    model_rows = [
        [m["name"], m["base"], m["license"], m["quantization"], m.get("adapter_path") or "—"]
        for m in result.models
    ]
    hash_rows = [
        [
            h.name,
            h.path or "—",
            "có" if h.exists else "không",
            h.declared[:12],
            (h.computed or "—")[:12],
            h.status,
        ]
        for h in result.hash_checks
        if h.status != "no_path"
    ]
    status = "HỢP LỆ" if result.ok else "LỖI"
    parts = [
        "# Báo cáo registry dữ liệu và mô hình\n",
        f"Sinh tự động bởi `python -m ctcv_data.pipeline registry` lúc {stamp}. "
        f"Trạng thái: **{status}**. Không sửa tay — sửa `datasets.yaml`/`models.yaml` "
        "rồi chạy lại.\n",
        "## Bộ dữ liệu\n",
        _table(
            ["Tên", "Phiên bản", "Loại nguồn", "Giấy phép", "Phân phối lại", "Dùng cho", "sha256"],
            dataset_rows,
        ),
        "## Mô hình\n",
        _table(["Tên", "Mô hình gốc", "Giấy phép", "Lượng tử hóa", "Adapter"], model_rows),
        "## Kiểm tra sha256\n",
        _table(["Tên", "Đường dẫn", "Tồn tại", "Khai báo", "Tính được", "Kết quả"], hash_rows),
        "## Vấn đề\n",
        "\n".join(f"- LỖI: {p}" for p in result.problems) or "- Không có lỗi.",
        "",
        "\n".join(f"- CẢNH BÁO: {w}" for w in result.warnings) or "- Không có cảnh báo.",
        "",
    ]
    return "\n".join(parts)


def run_registry(
    root: Path | None = None,
    directory: Path | None = None,
    *,
    update_hashes: bool = False,
    write_report: bool = True,
) -> RegistryResult:
    """Validate both registries, check hashes (fill ``pending`` on request), write REPORT.md."""
    root = root or REPO_ROOT
    directory = directory or registry_dir(root)
    result = RegistryResult(ok=True)
    for name in REGISTRY_SCHEMAS:
        try:
            entries = load_registry(name, directory)
        except ConfigError as exc:
            result.problems.append(exc.message_vi)
            continue
        result.problems.extend(validate_entries(name, entries, root))
        setattr(result, name, entries)
    result.hash_checks = check_hashes(result.datasets, root)
    for check in result.hash_checks:
        if check.status == "mismatch":
            result.problems.append(
                f"datasets.yaml[{check.name}]: sha256 khai báo khác với file {check.path}"
            )
        elif check.status == PENDING and check.computed:
            if update_hashes and update_sha256(
                directory / "datasets.yaml", check.name, check.computed
            ):
                check.status, check.declared = "match", check.computed
            else:
                result.warnings.append(
                    f"datasets.yaml[{check.name}]: sha256 đang 'pending', "
                    f"tính được {check.computed}"
                )
        elif check.status == "missing":
            result.warnings.append(f"datasets.yaml[{check.name}]: chưa có file {check.path}")
    result.ok = not result.problems
    if write_report:
        result.report_path = directory / REPORT_NAME
        result.report_path.write_text(render_report(result), encoding="utf-8")
    return result
