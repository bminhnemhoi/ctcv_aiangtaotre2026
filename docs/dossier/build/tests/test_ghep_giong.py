"""Tests for docs/dossier/dfl/video/ghep_giong.py (placing Vbee voice clips at scene start times)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "dfl" / "video" / "ghep_giong.py"
_SPEC = importlib.util.spec_from_file_location("ghep_giong", _PATH)
gg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gg)

SRT = """1
00:00:00,000 --> 00:00:16,000
Dòng một

2
00:00:16,000 --> 00:00:28,500
Dòng hai
"""


def test_parse_srt_reads_start_and_end() -> None:
    assert gg.parse_srt(SRT) == [(0.0, 16.0), (16.0, 28.5)]


def test_ffmpeg_command_delays_each_clip_to_its_cue(tmp_path: Path) -> None:
    clips = [tmp_path / "01.mp3", tmp_path / "02.mp3"]
    cmd = gg.ffmpeg_command(clips, gg.parse_srt(SRT), tmp_path / "giong.m4a")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=300|300" in graph
    assert "adelay=16300|16300" in graph
    assert "amix=inputs=2:normalize=0" in graph
    assert cmd[-1].endswith("giong.m4a")


def test_too_long_flags_only_overrunning_clips() -> None:
    msgs = gg.too_long([10.0, 12.5], gg.parse_srt(SRT))
    assert len(msgs) == 1 and msgs[0].startswith("Đoạn 02")


def test_find_clips_reports_missing_number(tmp_path: Path) -> None:
    (tmp_path / "01.mp3").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match="02"):
        gg.find_clips(tmp_path, 2)
    (tmp_path / "02.wav").write_bytes(b"")
    assert [p.name for p in gg.find_clips(tmp_path, 2)] == ["01.mp3", "02.wav"]
