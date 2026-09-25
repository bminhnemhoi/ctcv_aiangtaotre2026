"""Assemble the Data for Life 2026 video (ADR-007 C9) from slides, the recorded demo and subtitles.

    uv run python docs/dossier/dfl/video/make_video.py --dry-run          # in kế hoạch ffmpeg
    uv run python docs/dossier/dfl/video/make_video.py [--voice loi.m4a]  # ghép thật

Inputs: ``loi-thoai.yaml`` (segment order, slide seconds, subtitles), and under
``docs/dossier/out/dfl/video/``: ``timeline.json`` + ``raw/**/*.webm`` from
``record-demo.demo.ts`` and ``slides/*.png`` from ``figures.demo.ts``. Demo segments are cut at the
exact recorded marks (no estimate, no mock). Output: ``ctcv-dfl-2026.mp4`` and ``.srt`` (H.264
yuv420p, 1920x1080, burned-in Arial subtitles), checked with ffprobe: ≤ 180 s or exit 1.
ffmpeg runs with ``cwd`` = the output directory so no Windows path is escaped inside a filter.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = Path(__file__).resolve().parent / "loi-thoai.yaml"
OUT_DIR = REPO_ROOT / "docs" / "dossier" / "out" / "dfl" / "video"
OUTPUT_STEM = "ctcv-dfl-2026"
TIMELINE_NAME = "timeline.json"
CONCAT_NAME = "concat.txt"
WORK_DIR = "work"

SLIDES = ("01-van-de", "02-giai-phap", "03-kien-truc", "04-du-lieu", "05-so-lieu", "06-lo-trinh")
DEMO_STEPS = (
    "hoi-phi",
    "mo-nguon",
    "hoi-giay-to",
    "hoi-ngoai-kho",
    "hoi-otp",
    "can-bo-dang-nhap",
    "can-bo-tim",
    "can-bo-danh-dau",
    "can-bo-ket-qua",
)
MAX_SECONDS = 180.0
WIDTH, HEIGHT, FPS = 1920, 1080, 30
MAX_SUB_LINES, MAX_SUB_CHARS = 2, 42
# Subtitles live in a dark band under the content so they never cover the screen being shown.
# libass sizes are relative to PlayResY=288: FontSize 13 ≈ 49 px, MarginV 9 ≈ 34 px at 1080p.
SUB_BAND = 170
SUB_STYLE = (
    "FontName=Arial,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=9"
)
FIT = (
    f"scale={WIDTH}:{HEIGHT - SUB_BAND}:force_original_aspect_ratio=decrease,"
    f"pad={WIDTH}:{HEIGHT - SUB_BAND}:(ow-iw)/2:(oh-ih)/2:color=white,"
    f"pad={WIDTH}:{HEIGHT}:0:0:color=0x111827,setsar=1,fps={FPS},format=yuv420p"
)
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]


class VideoError(Exception):
    """Invalid input or failed check (message in Vietnamese)."""


@dataclass(frozen=True)
class Segment:
    """One entry of ``loi-thoai.yaml``."""

    id: str
    kind: str
    slide: str | None
    demo_step: str | None
    seconds: float | None
    est_seconds: float | None
    subtitle: str


@dataclass(frozen=True)
class Planned:
    """A segment placed on the output timeline."""

    segment: Segment
    start_ms: int
    duration_ms: int
    source_start_ms: int | None = None
    estimated: bool = False


@dataclass(frozen=True)
class Options:
    """Command-line options."""

    script: Path = SCRIPT_PATH
    out_dir: Path = OUT_DIR
    dry_run: bool = False
    voice: Path | None = None


# ------------------------------------------------------------------ inputs


def _check_subtitle(seg_id: str, text: str) -> None:
    lines = text.split("\n")
    if len(lines) > MAX_SUB_LINES:
        raise VideoError(f"{seg_id}: phụ đề quá {MAX_SUB_LINES} dòng.")
    for line in lines:
        if len(line) > MAX_SUB_CHARS:
            raise VideoError(
                f"{seg_id}: dòng phụ đề dài {len(line)} ký tự (tối đa {MAX_SUB_CHARS})."
            )


def _segment(raw: dict[str, Any]) -> Segment:
    seg = Segment(
        id=str(raw.get("id") or ""),
        kind=str(raw.get("kind") or ""),
        slide=raw.get("slide"),
        demo_step=raw.get("demo_step"),
        seconds=float(raw["seconds"]) if raw.get("seconds") is not None else None,
        est_seconds=float(raw["est_seconds"]) if raw.get("est_seconds") is not None else None,
        subtitle=str(raw.get("subtitle") or "").strip(),
    )
    if seg.kind == "slide" and (not seg.slide or not seg.seconds or seg.seconds <= 0):
        raise VideoError(f"{seg.id}: đoạn slide cần 'slide' và 'seconds' > 0.")
    if seg.kind == "demo" and (not seg.demo_step or seg.seconds is not None):
        raise VideoError(f"{seg.id}: đoạn demo cần 'demo_step' và không có 'seconds'.")
    if seg.kind not in {"slide", "demo"} or not seg.id:
        raise VideoError(f"Đoạn không hợp lệ: {raw!r}.")
    _check_subtitle(seg.id, seg.subtitle)
    return seg


def load_script(path: Path) -> list[Segment]:
    """Load and validate ``loi-thoai.yaml``."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("version") != 1 or not isinstance(data.get("segments"), list):
        raise VideoError(f"{path}: cần version: 1 và danh sách segments.")
    return [_segment(raw) for raw in data["segments"]]


def load_timeline(path: Path) -> dict[str, tuple[int, int]]:
    """Read ``timeline.json`` → ``{step id: (t_start_ms, t_end_ms)}``."""
    if not path.is_file():
        return {}
    marks: dict[str, tuple[int, int]] = {}
    for item in json.loads(path.read_text(encoding="utf-8")):
        start, end = int(item["t_start_ms"]), int(item["t_end_ms"])
        if start < 0 or end <= start:
            raise VideoError(f"timeline.json: mốc sai ở bước {item.get('id')}.")
        marks[str(item["id"])] = (start, end)
    return marks


def plan_segments(
    segments: list[Segment], timeline: dict[str, tuple[int, int]], *, allow_estimates: bool = False
) -> list[Planned]:
    """Place every segment on the output timeline (demo = exact recorded marks)."""
    planned: list[Planned] = []
    cursor = 0
    for seg in segments:
        if seg.kind == "slide":
            item = Planned(seg, cursor, round((seg.seconds or 0) * 1000))
        elif seg.demo_step in timeline:
            start, end = timeline[seg.demo_step]
            item = Planned(seg, cursor, end - start, source_start_ms=start)
        elif allow_estimates and seg.est_seconds:
            item = Planned(seg, cursor, round(seg.est_seconds * 1000), estimated=True)
        else:
            raise VideoError(f"timeline.json thiếu bước demo '{seg.demo_step}'.")
        planned.append(item)
        cursor += item.duration_ms
    return planned


def find_demo_video(raw_dir: Path) -> Path | None:
    """Newest ``*.webm`` recorded by Playwright under ``raw/``."""
    videos = (
        sorted(raw_dir.rglob("*.webm"), key=lambda p: p.stat().st_mtime) if raw_dir.is_dir() else []
    )
    return videos[-1] if videos else None


# ------------------------------------------------------------------ SRT and ffmpeg


def format_ts(ms: int) -> str:
    """SRT timestamp ``HH:MM:SS,mmm``."""
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_srt(planned: list[Planned]) -> str:
    """One cue per segment, spanning the whole segment."""
    cues = [
        f"{i}\n{format_ts(p.start_ms)} --> {format_ts(p.start_ms + p.duration_ms)}\n"
        f"{p.segment.subtitle}\n"
        for i, p in enumerate(planned, start=1)
    ]
    return "\n".join(cues)


def _work_file(index: int, planned: Planned) -> str:
    return f"{WORK_DIR}/seg_{index:02d}_{planned.segment.id}.mp4"


def _segment_command(index: int, item: Planned, out_dir: Path, video: Path) -> list[str]:
    duration = f"{item.duration_ms / 1000:.3f}"
    if item.segment.kind == "slide":
        png = (out_dir / "slides" / f"{Path(item.segment.slide or '').stem}.png").resolve()
        source = ["-framerate", str(FPS), "-loop", "1", "-t", duration, "-i", png.as_posix()]
    else:
        start = f"{(item.source_start_ms or 0) / 1000:.3f}"
        source = ["-ss", start, "-t", duration, "-i", video.resolve().as_posix()]
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *source,
            "-vf", FIT, "-an", *X264, "-r", str(FPS), _work_file(index, item)]  # fmt: skip


def concat_list(planned: list[Planned]) -> str:
    """Build the ffmpeg concat-demuxer list (paths relative to the output directory)."""
    return "".join(f"file '{_work_file(i, p)}'\n" for i, p in enumerate(planned, start=1))


def _final_command(voice: Path | None) -> list[str]:
    subtitles = f"subtitles={OUTPUT_STEM}.srt:force_style='{SUB_STYLE}'"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", CONCAT_NAME]  # fmt: skip
    if voice is not None:
        cmd += ["-i", voice.resolve().as_posix(), "-map", "0:v:0", "-map", "1:a:0"]
    cmd += ["-vf", subtitles, *X264, "-r", str(FPS)]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest"] if voice else ["-an"]
    return [*cmd, "-movflags", "+faststart", f"{OUTPUT_STEM}.mp4"]


def ffmpeg_commands(
    planned: list[Planned], *, out_dir: Path, video: Path, voice: Path | None
) -> list[list[str]]:
    """Per-segment encodes followed by the concat + subtitles pass (run with cwd=out_dir)."""
    segments = [_segment_command(i, p, out_dir, video) for i, p in enumerate(planned, start=1)]
    return [*segments, _final_command(voice)]


def check_output(duration: float, width: int, height: int) -> list[str]:
    """Problems with the final file (empty list = OK)."""
    problems = []
    if duration > MAX_SECONDS:
        problems.append(f"Video dài {duration:.1f} s, vượt {MAX_SECONDS:.0f} s.")
    if (width, height) != (WIDTH, HEIGHT):
        problems.append(f"Khung hình {width}x{height}, cần {WIDTH}x{HEIGHT}.")
    return problems


def probe(path: Path) -> tuple[float, int, int]:
    """Duration (s), width and height of ``path`` via ffprobe."""
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    info = json.loads(done.stdout)
    stream = info["streams"][0]
    return float(info["format"]["duration"]), int(stream["width"]), int(stream["height"])


# ------------------------------------------------------------------ run


def _missing_inputs(planned: list[Planned], out_dir: Path, video: Path | None) -> list[str]:
    missing = [] if video else [f"{out_dir / 'raw'}/**/*.webm (chạy record-demo.demo.ts)"]
    for item in planned:
        if item.segment.kind == "slide":
            png = out_dir / "slides" / f"{Path(item.segment.slide or '').stem}.png"
            if not png.is_file():
                missing.append(f"{png} (chạy figures.demo.ts)")
    return missing


def _print_plan(planned: list[Planned], commands: list[list[str]], out_dir: Path) -> None:
    total = sum(p.duration_ms for p in planned) / 1000
    print(f"Thư mục làm việc ffmpeg (cwd): {out_dir}")
    for p in planned:
        note = " (ước tính — chưa có timeline.json)" if p.estimated else ""
        print(f"  {format_ts(p.start_ms)}  {p.segment.id:<22} {p.duration_ms / 1000:6.2f} s{note}")
    print(f"Tổng: {total:.2f} s (tối đa {MAX_SECONDS:.0f} s)")
    print(f"--- {CONCAT_NAME}\n{concat_list(planned)}--- {OUTPUT_STEM}.srt\n{build_srt(planned)}")
    for cmd in commands:
        print(shlex.join(cmd))


def _encode(planned: list[Planned], commands: list[list[str]], out_dir: Path) -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise VideoError(f"Không tìm thấy {tool} trong PATH.")
    (out_dir / WORK_DIR).mkdir(parents=True, exist_ok=True)
    (out_dir / f"{OUTPUT_STEM}.srt").write_text(build_srt(planned), encoding="utf-8")
    (out_dir / CONCAT_NAME).write_text(concat_list(planned), encoding="utf-8")
    for cmd in commands:
        done = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, errors="replace")
        if done.returncode != 0:
            raise VideoError(f"ffmpeg lỗi ({cmd[-1]}):\n{done.stderr[-2000:]}")
    duration, width, height = probe(out_dir / f"{OUTPUT_STEM}.mp4")
    problems = check_output(duration, width, height)
    if problems:
        raise VideoError(" ".join(problems))
    print(f"Xong: {out_dir / (OUTPUT_STEM + '.mp4')} ({duration:.1f} s, {width}x{height})")


def run(opts: Options) -> int:
    """Plan (and unless dry-run, encode) the video; return the exit code."""
    segments = load_script(opts.script)
    timeline = load_timeline(opts.out_dir / TIMELINE_NAME)
    if not timeline and not opts.dry_run:
        raise VideoError(f"Chưa có {opts.out_dir / TIMELINE_NAME} (chạy record-demo.demo.ts).")
    if opts.voice is not None and not opts.voice.is_file():
        raise VideoError(f"Không thấy file lời thu âm {opts.voice}.")
    planned = plan_segments(segments, timeline, allow_estimates=opts.dry_run)
    video = find_demo_video(opts.out_dir / "raw")
    commands = ffmpeg_commands(
        planned, out_dir=opts.out_dir, video=video or Path("raw/video.webm"), voice=opts.voice
    )
    total = sum(p.duration_ms for p in planned) / 1000
    if opts.dry_run:
        _print_plan(planned, commands, opts.out_dir)
        for item in _missing_inputs(planned, opts.out_dir, video):
            print(f"THIẾU (cần trước khi ghép thật): {item}")
    if total > MAX_SECONDS:
        raise VideoError(
            f"Kế hoạch dài {total:.1f} s > {MAX_SECONDS:.0f} s. Rút slide (mỗi slide ≥ 8 s) "
            "hoặc tua nhanh đoạn chờ có chữ 'tua nhanh' (kich-ban-video.md)."
        )
    if opts.dry_run:
        return 0
    missing = _missing_inputs(planned, opts.out_dir, video)
    if missing:
        raise VideoError("Thiếu đầu vào: " + "; ".join(missing))
    _encode(planned, commands, opts.out_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="chỉ in kế hoạch ffmpeg")
    parser.add_argument("--voice", type=Path, default=None, help="lời thuyết minh do người thu")
    parser.add_argument("--script", type=Path, default=SCRIPT_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    opts = Options(script=args.script, out_dir=args.out_dir, dry_run=args.dry_run, voice=args.voice)
    try:
        return run(opts)
    except (VideoError, OSError, ValueError, KeyError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
