from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.validate import expand_paths, main

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_ID = "chuyen-khoan-qr"
SAMPLE_PATH = SCENARIOS_DIR / f"{SAMPLE_ID}.json"
WriteJson = Callable[[Path, Any], Path]


def test_valid_file_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(SAMPLE_PATH)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK") and "1 kịch bản, 0 file lỗi" in out


def test_default_scans_scenarios_dir(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert SAMPLE_PATH.name in capsys.readouterr().out


def test_invalid_dir_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(INVALID_DIR)]) == 1
    out = capsys.readouterr().out
    assert out.count("LỖI") == len(list(INVALID_DIR.glob("*.json")))
    assert "[START_SCREEN_MISSING]" in out


def test_quiet_hides_ok_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--quiet", str(SAMPLE_PATH)]) == 0
    assert "OK" not in capsys.readouterr().out


def test_missing_file_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "nope.json")]) == 1
    assert "[FILE_NOT_FOUND]" in capsys.readouterr().out


def test_duplicate_ids_across_files(
    scenarios_dir: Path,
    sample_dict: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    write_json: WriteJson,
) -> None:
    write_json(scenarios_dir / "zz-ban-sao.json", sample_dict)
    assert main([str(scenarios_dir)]) == 1
    out = capsys.readouterr().out
    assert "[DUPLICATE_SCENARIO_ID]" in out
    assert "2 kịch bản, 1 file lỗi" in out


def test_duplicate_detection_survives_unreadable_files(
    scenarios_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (scenarios_dir / "hong.json").write_text("{", encoding="utf-8")
    (scenarios_dir / "mang.json").write_text("[]", encoding="utf-8")
    assert main([str(scenarios_dir)]) == 1
    out = capsys.readouterr().out
    assert "[JSON_INVALID]" in out and "[NOT_AN_OBJECT]" in out


def test_expand_paths_mixes_files_and_dirs(scenarios_dir: Path) -> None:
    paths = expand_paths([str(scenarios_dir), str(SAMPLE_PATH)])
    assert paths == [scenarios_dir / SAMPLE_PATH.name, SAMPLE_PATH]


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ctcv_sandbox.validate", str(SAMPLE_PATH)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
