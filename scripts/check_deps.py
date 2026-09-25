"""Dependency allow-list gate for ``make audit`` (brief D26).

Every third-party package in ``uv.lock`` (and ``pnpm-lock.yaml`` when present) must be
listed in ``config/allowed-deps.yaml``; no listed runtime package may carry a banned
license (AGPL/GPL/CC-NC); banned packages (``ultralytics``, ``yolov5``) must not appear
anywhere. Missing entries are printed as ready-to-paste YAML so the owning epic can
add them deliberately.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DEPS = Path("config") / "allowed-deps.yaml"
PNPM_PACKAGE_RE = re.compile(r"^/?(@?[^@/][^@]*)@")


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize(name: str) -> str:
    """PEP 503-style normalisation shared by both ecosystems."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def load_allowed(root: Path) -> dict[str, Any]:
    """Read config/allowed-deps.yaml (raises FileNotFoundError when absent)."""
    return yaml.safe_load((root / ALLOWED_DEPS).read_text(encoding="utf-8"))


def locked_python(root: Path) -> dict[str, str]:
    """``normalized name → version`` for third-party packages in uv.lock."""
    path = root / "uv.lock"
    if not path.is_file():
        return {}
    packages = tomllib.loads(path.read_text(encoding="utf-8")).get("package", [])
    return {
        normalize(p["name"]): p.get("version", "?")
        for p in packages
        if "editable" not in p.get("source", {}) and "virtual" not in p.get("source", {})
    }


def locked_node(root: Path) -> dict[str, str]:
    """``normalized name → version`` for packages in pnpm-lock.yaml (empty when absent)."""
    path = root / "pnpm-lock.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: dict[str, str] = {}
    for key in data.get("packages") or {}:
        match = PNPM_PACKAGE_RE.match(str(key))
        if match:
            found[normalize(match.group(1))] = str(key).rsplit("@", 1)[-1]
    return found


def _entries(allowed: dict[str, Any], ecosystem: str) -> dict[str, dict[str, Any]]:
    return {normalize(e["name"]): e for e in allowed.get(ecosystem) or []}


def find_problems(
    allowed: dict[str, Any], python: dict[str, str], node: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Return ``(problems, missing_yaml_snippets)``."""
    problems: list[str] = []
    snippets: list[str] = []
    banned_pkgs = {normalize(n) for n in allowed.get("banned_packages", [])}
    patterns = [re.compile(p) for p in allowed.get("banned_license_patterns", [])]
    for ecosystem, locked in (("python", python), ("node", node)):
        entries = _entries(allowed, ecosystem)
        for name, version in sorted(locked.items()):
            if name in banned_pkgs:
                problems.append(f"{ecosystem}: gói bị cấm '{name}' có trong lockfile.")
            if name not in entries:
                problems.append(
                    f"{ecosystem}: '{name}' ({version}) chưa có trong config/allowed-deps.yaml."
                )
                snippets.append(
                    f"  - {{ name: {name}, license: UNKNOWN, runtime: false, "
                    "reason: TODO, epic: E01 }"
                )
        for name, entry in entries.items():
            if name in banned_pkgs:
                problems.append(
                    f"{ecosystem}: '{name}' nằm trong banned_packages nhưng vẫn được liệt kê."
                )
            if entry.get("runtime") and any(
                p.search(str(entry.get("license", ""))) for p in patterns
            ):
                problems.append(
                    f"{ecosystem}: '{name}' là runtime nhưng giấy phép '{entry['license']}' bị cấm."
                )
            if str(entry.get("license", "")).upper() == "UNKNOWN":
                problems.append(f"{ecosystem}: '{name}' chưa xác định giấy phép (UNKNOWN).")
    return problems, snippets


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        allowed = load_allowed(args.root)
    except FileNotFoundError:
        print(f"LỖI: thiếu {ALLOWED_DEPS} (D26).")
        return 1
    python, node = locked_python(args.root), locked_node(args.root)
    problems, snippets = find_problems(allowed, python, node)
    for problem in problems:
        print(f"LỖI: {problem}")
    if snippets:
        print("Thêm vào config/allowed-deps.yaml (điền giấy phép thật, lý do và epic):")
        print("\n".join(snippets))
    if problems:
        return 1
    print(
        f"allowed-deps OK: {len(python)} gói Python, {len(node)} gói Node "
        "đều nằm trong danh sách cho phép."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
