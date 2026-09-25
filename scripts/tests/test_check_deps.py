from __future__ import annotations

from pathlib import Path

import check_deps
import pytest
import yaml

ALLOWED = {
    "version": 1,
    "banned_packages": ["ultralytics"],
    "banned_license_patterns": ["AGPL", r"\bGPL", "NC"],
    "python": [
        {"name": "PyYAML", "license": "MIT", "runtime": True, "reason": "yaml", "epic": "E01"},
        {"name": "ruff", "license": "MIT", "runtime": False, "reason": "lint", "epic": "E01"},
    ],
    "node": [{"name": "react", "license": "MIT", "runtime": True, "reason": "ui", "epic": "E02"}],
}


def test_normalize() -> None:
    assert check_deps.normalize("PyYAML") == "pyyaml"
    assert check_deps.normalize("typing_extensions") == "typing-extensions"
    assert check_deps.normalize("ruamel.yaml") == "ruamel-yaml"


def test_no_problems_when_everything_listed() -> None:
    problems, snippets = check_deps.find_problems(
        ALLOWED, {"pyyaml": "6.0", "ruff": "0.16"}, {"react": "18"}
    )
    assert problems == [] and snippets == []


def test_missing_package_reports_snippet() -> None:
    problems, snippets = check_deps.find_problems(ALLOWED, {"pyyaml": "6.0", "httpx": "0.28"}, {})
    assert any("'httpx'" in p for p in problems)
    assert snippets and "name: httpx" in snippets[0]


def test_banned_package_and_license() -> None:
    allowed = {
        **ALLOWED,
        "python": [
            *ALLOWED["python"],
            {
                "name": "gpltool",
                "license": "GPL-3.0",
                "runtime": True,
                "reason": "x",
                "epic": "E01",
            },
        ],
    }
    problems, _ = check_deps.find_problems(allowed, {"ultralytics": "8", "gpltool": "1"}, {})
    assert any("bị cấm 'ultralytics'" in p for p in problems)
    assert any("giấy phép 'GPL-3.0' bị cấm" in p for p in problems)


def test_lgpl_not_matched_by_gpl_pattern() -> None:
    allowed = {
        **ALLOWED,
        "python": [
            {"name": "x", "license": "LGPL-2.1", "runtime": True, "reason": "x", "epic": "E01"}
        ],
    }
    problems, _ = check_deps.find_problems(allowed, {"x": "1"}, {})
    assert problems == []


def test_unknown_license_is_a_problem() -> None:
    allowed = {
        **ALLOWED,
        "python": [
            {"name": "x", "license": "UNKNOWN", "runtime": False, "reason": "x", "epic": "E01"}
        ],
    }
    problems, _ = check_deps.find_problems(allowed, {"x": "1"}, {})
    assert any("UNKNOWN" in p for p in problems)


def test_locked_node_parses_pnpm_lock(tmp_path: Path) -> None:
    (tmp_path / "pnpm-lock.yaml").write_text(
        "lockfileVersion: '9.0'\npackages:\n  react@18.3.1: {}\n  '@types/node@20.1.0': {}\n",
        encoding="utf-8",
    )
    assert check_deps.locked_node(tmp_path) == {"react": "18.3.1", "@types/node": "20.1.0"}
    assert check_deps.locked_node(tmp_path / "nope") == {}


def test_locked_python_skips_workspace_members(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "ctcv-core"\nversion = "0.1.0"\n'
        'source = { editable = "libs/core" }\n'
        '[[package]]\nname = "PyYAML"\nversion = "6.0.2"\n'
        'source = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )
    assert check_deps.locked_python(tmp_path) == {"pyyaml": "6.0.2"}


def test_main_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check_deps.main(["--root", str(tmp_path)]) == 1
    assert "allowed-deps.yaml" in capsys.readouterr().out


def test_main_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "allowed-deps.yaml").write_text(
        yaml.safe_dump(ALLOWED), encoding="utf-8"
    )
    assert check_deps.main(["--root", str(tmp_path)]) == 0
    assert "allowed-deps OK" in capsys.readouterr().out


def test_real_repo_lockfile_is_fully_allowed() -> None:
    allowed = check_deps.load_allowed(check_deps.REPO_ROOT)
    problems, _ = check_deps.find_problems(
        allowed,
        check_deps.locked_python(check_deps.REPO_ROOT),
        check_deps.locked_node(check_deps.REPO_ROOT),
    )
    assert problems == []
