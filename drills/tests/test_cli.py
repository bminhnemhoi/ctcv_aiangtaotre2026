from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ctcv_core.paths import DRILLS_DIR
from ctcv_drills.validate import expand_paths, main

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_KEY = "gia-danh-cong-an-goi-dien"
SAMPLE_PATH = DRILLS_DIR / f"{SAMPLE_KEY}.json"
WriteJson = Callable[[Path, Any], Path]


def test_valid_file_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(SAMPLE_PATH)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK") and "1 kịch bản, 0 file lỗi" in out


def test_default_scans_drills_dir(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert SAMPLE_PATH.name in capsys.readouterr().out


def test_invalid_dir_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(INVALID_DIR)]) == 1
    out = capsys.readouterr().out
    assert out.count("LỖI") == len(list(INVALID_DIR.glob("*.json")))
    assert "[FORBIDDEN_FIELD]" in out and "[UTTERANCE_MISSING_TAG]" in out


def test_quiet_hides_ok_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--quiet", str(SAMPLE_PATH)]) == 0
    assert "OK" not in capsys.readouterr().out


def test_missing_file_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "nope.json")]) == 1
    assert "[FILE_NOT_FOUND]" in capsys.readouterr().out


def test_duplicate_key_variant_across_files(
    drills_dir: Path,
    sample_dict: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    write_json: WriteJson,
) -> None:
    write_json(drills_dir / f"{SAMPLE_KEY}-2.json", sample_dict)
    assert main([str(drills_dir)]) == 1
    out = capsys.readouterr().out
    assert "[KEY_FILENAME_MISMATCH]" in out and "[DUPLICATE_DRILL]" in out


def test_duplicate_detection_survives_unreadable_files(
    drills_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (drills_dir / "hong.json").write_text("{", encoding="utf-8")
    (drills_dir / "mang.json").write_text("[]", encoding="utf-8")
    (drills_dir / "trong.json").write_text("{}", encoding="utf-8")
    assert main([str(drills_dir)]) == 1
    out = capsys.readouterr().out
    assert "[JSON_INVALID]" in out and "[NOT_AN_OBJECT]" in out and "[FIELD_MISSING]" in out


def test_expand_paths_mixes_files_and_dirs(drills_dir: Path) -> None:
    paths = expand_paths([str(drills_dir), str(SAMPLE_PATH)])
    assert paths == [drills_dir / SAMPLE_PATH.name, SAMPLE_PATH]


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ctcv_drills.validate", str(SAMPLE_PATH)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
