"""Place per-scene voice clips (01.mp3 … 15.mp3) at their subtitle start times as one voice track.

Usage (Git Bash, repo root):
    V=docs/dossier/out/dfl/v2/video
    uv run python docs/dossier/dfl/video/ghep_giong.py <thư mục 15 file> \
        --srt $V/ctcv-dfl-2026.srt --out $V/giong.m4a
then rebuild the video with the voice:
    uv run python docs/dossier/dfl/video/make_video.py --out-dir $V --voice $V/giong.m4a

Clip ``NN`` is delayed to the start of subtitle ``NN`` plus a short lead. A clip longer than its
scene is reported (it would run into the next scene) so the user can regenerate it faster instead
of it being cut silently.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LEAD_S = 0.3
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg")
_TIME = r"(\d\d):(\d\d):(\d\d),(\d{3})"
_CUE = re.compile(_TIME + r"\s*-->\s*" + _TIME)


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(text: str) -> list[tuple[float, float]]:
    """Return (start, end) seconds for every cue, in file order."""
    return [(_seconds(*g[:4]), _seconds(*g[4:])) for g in _CUE.findall(text)]


def find_clips(folder: Path, count: int) -> list[Path]:
    """Return clips named 01.* … NN.*; raise if one is missing."""
    clips = []
    for i in range(1, count + 1):
        hits = [p for p in folder.glob(f"{i:02d}.*") if p.suffix.lower() in AUDIO_EXTS]
        if not hits:
            raise FileNotFoundError(f"Thiếu file giọng {i:02d} (mp3/wav/m4a/ogg) trong {folder}")
        clips.append(hits[0])
    return clips


def probe_seconds(path: Path) -> float:
    """Duration of an audio file via ffprobe."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
    out = subprocess.run([*cmd, str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def too_long(durations: list[float], cues: list[tuple[float, float]]) -> list[str]:
    """Human-readable warnings for clips that overrun their scene."""
    msgs = []
    for i, (dur, (start, end)) in enumerate(zip(durations, cues, strict=True), 1):
        slot = end - start - LEAD_S
        if dur > slot:
            msgs.append(
                f"Đoạn {i:02d} dài {dur:.1f} s, cảnh chỉ có {slot:.1f} s — "
                "tạo lại nhanh hơn (tốc độ 1.1–1.2)."
            )
    return msgs


def ffmpeg_command(clips: list[Path], cues: list[tuple[float, float]], out: Path) -> list[str]:
    """Build the ffmpeg call that delays each clip to its cue start and mixes one AAC track."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for clip in clips:
        cmd += ["-i", str(clip)]
    parts = []
    for i, (start, _end) in enumerate(cues):
        delay = int(round((start + LEAD_S) * 1000))
        parts.append(f"[{i}:a]aresample=48000,adelay={delay}|{delay}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(cues)))
    parts.append(f"{mix}amix=inputs={len(cues)}:normalize=0:dropout_transition=0[out]")
    audio = ["-map", "[out]", "-c:a", "aac", "-b:a", "160k", str(out)]
    return [*cmd, "-filter_complex", ";".join(parts), *audio]


def main(argv: list[str] | None = None) -> int:
    """Mix the clips in ``folder`` into ``--out`` following the cues of ``--srt``."""
    parser = argparse.ArgumentParser(description="Ghép 15 đoạn giọng Vbee vào đúng mốc cảnh")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    cues = parse_srt(args.srt.read_text(encoding="utf-8"))
    clips = find_clips(args.folder, len(cues))
    warnings = too_long([probe_seconds(c) for c in clips], cues)
    for msg in warnings:
        print("CẢNH BÁO:", msg, file=sys.stderr)
    subprocess.run(ffmpeg_command(clips, cues, args.out), check=True)
    print(f"Xong: {args.out} ({len(clips)} đoạn, {len(warnings)} cảnh báo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
