"""Tests for docs/dossier/dfl/video/make_video.py: SRT from a timeline, ffmpeg plan (dry-run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
VIDEO_DIR = REPO / "docs" / "dossier" / "dfl" / "video"
sys.path.insert(0, str(VIDEO_DIR))

import make_video as mv  # noqa: E402

SCRIPT_YAML = """
version: 1
target_seconds: 40
segments:
  - {id: s01, kind: slide, slide: 01-van-de.html, demo_step: null, seconds: 5,
     subtitle: "Dòng một\\nDòng hai"}
  - {id: d01, kind: demo, slide: null, demo_step: hoi-phi, est_seconds: 12, subtitle: "Hỏi phí"}
  - {id: d02, kind: demo, slide: null, demo_step: mo-nguon, est_seconds: 8, subtitle: "Nguồn"}
  - {id: s02, kind: slide, slide: 06-lo-trinh.html, demo_step: null, seconds: 4, subtitle: "Kết"}
"""

TIMELINE = [
    {"id": "hoi-phi", "t_start_ms": 1500, "t_end_ms": 13750},
    {"id": "mo-nguon", "t_start_ms": 14000, "t_end_ms": 20000},
]


def _write(tmp_path: Path, script: str = SCRIPT_YAML, timeline: object = TIMELINE) -> mv.Options:
    script_path = tmp_path / "loi-thoai.yaml"
    script_path.write_text(script, encoding="utf-8")
    out = tmp_path / "out"
    (out / "raw" / "record-demo-chromium").mkdir(parents=True)
    (out / "raw" / "record-demo-chromium" / "video.webm").write_bytes(b"webm")
    (out / "slides").mkdir()
    for name in ("01-van-de", "06-lo-trinh"):
        (out / "slides" / f"{name}.png").write_bytes(b"png")
    if timeline is not None:
        (out / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    return mv.Options(script=script_path, out_dir=out, dry_run=True, voice=None)


def test_format_timestamp() -> None:
    assert mv.format_ts(0) == "00:00:00,000"
    assert mv.format_ts(3_723_456) == "01:02:03,456"


def test_real_script_is_valid() -> None:
    segments = mv.load_script(VIDEO_DIR / "loi-thoai.yaml")
    slides = [s for s in segments if s.kind == "slide"]
    demos = [s for s in segments if s.kind == "demo"]
    assert [s.slide for s in slides] == [f"{n}.html" for n in mv.SLIDES]
    assert [s.demo_step for s in demos] == list(mv.DEMO_STEPS)


def test_subtitle_limits_are_enforced(tmp_path: Path) -> None:
    bad = SCRIPT_YAML.replace("Hỏi phí", "x" * 43)
    path = tmp_path / "bad.yaml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(mv.VideoError, match="42"):
        mv.load_script(path)
    three = SCRIPT_YAML.replace("Hỏi phí", "a\\nb\\nc")
    path.write_text(three, encoding="utf-8")
    with pytest.raises(mv.VideoError, match="2 dòng"):
        mv.load_script(path)


def test_srt_uses_slide_seconds_and_real_timeline(tmp_path: Path) -> None:
    opts = _write(tmp_path)
    segments = mv.load_script(opts.script)
    timeline = mv.load_timeline(opts.out_dir / "timeline.json")
    planned = mv.plan_segments(segments, timeline, allow_estimates=False)
    assert [(p.start_ms, p.duration_ms) for p in planned] == [
        (0, 5000),
        (5000, 12250),
        (17250, 6000),
        (23250, 4000),
    ]
    assert planned[1].source_start_ms == 1500
    srt = mv.build_srt(planned)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:05,000\nDòng một\nDòng hai\n\n")
    assert "2\n00:00:05,000 --> 00:00:17,250\nHỏi phí\n" in srt
    assert "4\n00:00:23,250 --> 00:00:27,250\nKết\n" in srt


def test_missing_timeline_step_is_an_error_unless_estimating(tmp_path: Path) -> None:
    opts = _write(tmp_path, timeline=TIMELINE[:1])
    segments = mv.load_script(opts.script)
    timeline = mv.load_timeline(opts.out_dir / "timeline.json")
    with pytest.raises(mv.VideoError, match="mo-nguon"):
        mv.plan_segments(segments, timeline, allow_estimates=False)
    planned = mv.plan_segments(segments, timeline, allow_estimates=True)
    assert planned[2].estimated is True and planned[2].duration_ms == 8000


def test_bad_timeline_is_rejected(tmp_path: Path) -> None:
    opts = _write(tmp_path, timeline=[{"id": "hoi-phi", "t_start_ms": 900, "t_end_ms": 100}])
    with pytest.raises(mv.VideoError, match="hoi-phi"):
        mv.load_timeline(opts.out_dir / "timeline.json")


def test_ffmpeg_plan(tmp_path: Path) -> None:
    opts = _write(tmp_path)
    segments = mv.load_script(opts.script)
    planned = mv.plan_segments(segments, mv.load_timeline(opts.out_dir / "timeline.json"))
    video = mv.find_demo_video(opts.out_dir / "raw")
    assert video is not None
    commands = mv.ffmpeg_commands(planned, out_dir=opts.out_dir, video=video, voice=None)
    assert len(commands) == len(planned) + 1
    slide = commands[0]
    assert slide[:1] == ["ffmpeg"]
    assert ["-loop", "1"] == slide[slide.index("-loop") : slide.index("-loop") + 2]
    assert slide[slide.index("-t") + 1] == "5.000"
    assert slide[slide.index("-i") + 1].endswith("slides/01-van-de.png")
    demo = " ".join(commands[1])
    assert "-ss 1.500 -t 12.250" in demo
    # Content is fitted above a dark subtitle band so burned-in subtitles never cover the screen.
    assert f"scale=1920:{1080 - mv.SUB_BAND}:force_original_aspect_ratio=decrease" in demo
    assert "pad=1920:1080:0:0:color=0x111827" in demo
    assert commands[1][-1] == "work/seg_02_d01.mp4"
    final = commands[-1]
    joined = " ".join(final)
    assert "-f concat -safe 0 -i concat.txt" in joined
    vf = final[final.index("-vf") + 1]
    assert vf == f"subtitles=ctcv-dfl-2026.srt:force_style='{mv.SUB_STYLE}'"
    assert "FontName=Arial" in mv.SUB_STYLE and "Alignment=2" in mv.SUB_STYLE
    assert "libx264" in final and "yuv420p" in final
    assert "-an" in final
    assert final[-1] == "ctcv-dfl-2026.mp4"
    concat = mv.concat_list(planned)
    assert concat.splitlines()[0] == "file 'work/seg_01_s01.mp4'"


def test_voice_track_is_mapped(tmp_path: Path) -> None:
    opts = _write(tmp_path)
    voice = tmp_path / "loi.m4a"
    voice.write_bytes(b"m4a")
    segments = mv.load_script(opts.script)
    planned = mv.plan_segments(segments, mv.load_timeline(opts.out_dir / "timeline.json"))
    final = mv.ffmpeg_commands(planned, out_dir=opts.out_dir, video=Path("v.webm"), voice=voice)[-1]
    joined = " ".join(final)
    assert voice.resolve().as_posix() in final
    assert "-map 0:v:0 -map 1:a:0" in joined
    assert "-c:a aac" in joined and "-shortest" in final
    assert "-an" not in final


def test_output_checks() -> None:
    assert mv.check_output(179.9, 1920, 1080) == []
    problems = mv.check_output(181.0, 1280, 720)
    assert any("180" in p for p in problems) and any("1920x1080" in p for p in problems)


def test_dry_run_prints_plan_without_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    opts = _write(tmp_path)
    args = ["--dry-run", "--script", str(opts.script), "--out-dir", str(opts.out_dir)]
    assert mv.main(args) == 0
    out = capsys.readouterr().out
    assert "ffmpeg" in out and "concat.txt" in out
    assert "00:00:27,250" in out  # SRT preview uses the timeline
    assert not (opts.out_dir / "ctcv-dfl-2026.mp4").exists()
    assert not (opts.out_dir / "ctcv-dfl-2026.srt").exists()


def test_dry_run_without_recording_uses_estimates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    opts = _write(tmp_path, timeline=None)
    args = ["--dry-run", "--script", str(opts.script), "--out-dir", str(opts.out_dir)]
    assert mv.main(args) == 0
    assert "ước tính" in capsys.readouterr().out


def test_plan_over_budget_fails(tmp_path: Path) -> None:
    long = [{"id": "hoi-phi", "t_start_ms": 0, "t_end_ms": 200_000}, TIMELINE[1]]
    opts = _write(tmp_path, timeline=long)
    args = ["--dry-run", "--script", str(opts.script), "--out-dir", str(opts.out_dir)]
    assert mv.main(args) == 1


def test_real_run_requires_recording(tmp_path: Path) -> None:
    opts = _write(tmp_path, timeline=None)
    args = ["--script", str(opts.script), "--out-dir", str(opts.out_dir)]
    assert mv.main(args) == 1
