from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

import pytest

from ctcv_speech.cache import (
    DEFAULT_VOICE,
    cache_key,
    cache_path,
    is_cache_key,
    is_cached,
    normalise_text,
    normalise_voice,
)

LINE = "Bác bấm nút xanh có chữ Tiếp tục nhé."


def test_normalise_collapses_whitespace_case_and_nfc():
    decomposed = unicodedata.normalize("NFD", "  Bác   bấm\tnút\n xanh ")
    assert normalise_text(decomposed) == "bác bấm nút xanh"


def test_cache_key_is_sha256_of_voice_and_normalised_text():
    expected = hashlib.sha256(f"{DEFAULT_VOICE}\n{normalise_text(LINE)}".encode()).hexdigest()
    assert cache_key(LINE) == expected
    assert len(cache_key(LINE)) == 64


def test_cache_key_ignores_spacing_case_and_normal_form():
    variants = [
        LINE,
        f"  {LINE}  ",
        LINE.upper(),
        unicodedata.normalize("NFD", LINE),
        "bác  bấm nút xanh có chữ tiếp tục nhé.",
    ]
    assert len({cache_key(v) for v in variants}) == 1


def test_cache_key_changes_with_text_and_voice():
    assert cache_key(LINE) != cache_key("Bác bấm nút đỏ có chữ Dừng nhé.")
    assert cache_key(LINE, voice="nam") != cache_key(LINE, voice="bac")
    assert cache_key(LINE, voice=" NAM ") == cache_key(LINE, voice="nam")
    assert cache_key(LINE, voice="") == cache_key(LINE)


def test_cache_key_accepts_none_voice_and_normalises_voice_like_text():
    # TtsIn.voice is `str | None`; None and blank both mean the default voice.
    assert cache_key(LINE, voice=None) == cache_key(LINE)
    assert cache_key(LINE, voice="  ") == cache_key(LINE)
    # The voice name goes through the same NFC + whitespace + casefold normalisation as text.
    nfd_voice = unicodedata.normalize("NFD", "Giọng Nữ")
    assert cache_key(LINE, voice=nfd_voice) == cache_key(LINE, voice="giọng  nữ")
    assert normalise_voice(None) == DEFAULT_VOICE
    assert normalise_voice("  Giọng Nữ ") == "giọng nữ"


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_cache_key_rejects_blank_text(blank: str):
    with pytest.raises(ValueError, match="rỗng"):
        cache_key(blank)


def test_cache_path_fans_out_by_key_prefix(tmp_path: Path):
    key = cache_key(LINE)
    path = cache_path(tmp_path, key)
    assert path == tmp_path / key[:2] / f"{key}.wav"
    assert cache_path(tmp_path, key, ext=".mp3").suffix == ".mp3"


@pytest.mark.parametrize(
    "bad_key",
    [
        "../../etc/passwd",
        "..",
        "",
        "abc",
        "A" * 64,  # uppercase hex is not what cache_key produces
        "g" * 64,  # not hex at all
        "0" * 63,
        "0" * 65,
        "0" * 62 + "/x",
        12345,
        None,
    ],
)
def test_cache_path_rejects_keys_that_are_not_sha256_digests(tmp_path: Path, bad_key):
    assert is_cache_key(bad_key) is False
    with pytest.raises(ValueError, match="Khóa cache"):
        cache_path(tmp_path, bad_key)
    with pytest.raises(ValueError, match="Khóa cache"):
        is_cached(tmp_path, bad_key)


@pytest.mark.parametrize("bad_ext", ["../x", "wav/../..", "", "mp3.exe", ".", "a" * 9, 3])
def test_cache_path_rejects_extensions_that_carry_path_segments(tmp_path: Path, bad_ext):
    with pytest.raises(ValueError, match="Đuôi tệp"):
        cache_path(tmp_path, cache_key(LINE), ext=bad_ext)


def test_cache_path_never_escapes_the_cache_dir(tmp_path: Path):
    key = cache_key(LINE)
    path = cache_path(tmp_path, key, ext="ogg")
    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert is_cache_key(key) is True


def test_is_cached_reflects_disk(tmp_path: Path):
    key = cache_key(LINE)
    assert is_cached(tmp_path, key) is False
    path = cache_path(tmp_path, key)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"RIFF")
    assert is_cached(tmp_path, key) is True
