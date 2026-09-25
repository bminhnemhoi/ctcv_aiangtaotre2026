"""Cache keys and paths for synthesised speech.

The coach repeats a few hundred lines (``coach_line``, ``hint``, "3 việc phải làm"), so TTS
output is cached by content: the key is the SHA-256 of the voice name plus the normalised
text. Normalisation is deliberately loose (NFC, collapsed whitespace, case-folded) because
those differences do not change how a sentence is spoken. ``cache_path`` only accepts keys
produced by ``cache_key`` (64 lowercase hex characters) so a key can never carry a path
segment into the cache directory.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

DEFAULT_VOICE = "default"
DEFAULT_AUDIO_EXT = "wav"
_WHITESPACE_RE = re.compile(r"\s+")
_KEY_RE = re.compile(r"[0-9a-f]{64}")
_EXT_RE = re.compile(r"\.?[A-Za-z0-9]{1,8}")


def normalise_text(text: str) -> str:
    """Return ``text`` NFC-normalised, whitespace-collapsed, stripped and case-folded."""
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", text)).strip().casefold()


def normalise_voice(voice: str | None) -> str:
    """Return the voice name normalised like text; ``None`` or blank means ``DEFAULT_VOICE``."""
    return normalise_text(voice or "") or DEFAULT_VOICE


def cache_key(text: str, voice: str | None = DEFAULT_VOICE) -> str:
    """Return the SHA-256 hex digest identifying ``text`` spoken by ``voice``.

    ``voice`` may be ``None`` (the ``TtsIn.voice`` contract) and is normalised the same way
    as the text, so ``"Nữ"`` and its NFD spelling share one clip.

    Raises:
        ValueError: when ``text`` is blank after normalisation.
    """
    normalised = normalise_text(text)
    if not normalised:
        raise ValueError("Văn bản rỗng, không tạo được khóa cache TTS.")
    payload = f"{normalise_voice(voice)}\n{normalised}".encode()
    return hashlib.sha256(payload).hexdigest()


def is_cache_key(key: object) -> bool:
    """True when ``key`` is a lowercase 64-hex SHA-256 digest as produced by ``cache_key``."""
    return isinstance(key, str) and _KEY_RE.fullmatch(key) is not None


def cache_path(cache_dir: Path, key: str, ext: str = DEFAULT_AUDIO_EXT) -> Path:
    """Return ``<cache_dir>/<key[:2]>/<key>.<ext>`` (two-level fan-out keeps directories small).

    Raises:
        ValueError: when ``key`` is not a ``cache_key`` digest or ``ext`` is not a short
            alphanumeric extension — neither may smuggle a path segment into ``cache_dir``.
    """
    if not is_cache_key(key):
        raise ValueError(f"Khóa cache TTS không hợp lệ (cần 64 ký tự hex thường): {key!r}")
    if not isinstance(ext, str) or _EXT_RE.fullmatch(ext) is None:
        raise ValueError(f"Đuôi tệp audio không hợp lệ (chỉ chữ và số, tối đa 8 ký tự): {ext!r}")
    return Path(cache_dir) / key[:2] / f"{key}.{ext.lstrip('.')}"


def is_cached(cache_dir: Path, key: str, ext: str = DEFAULT_AUDIO_EXT) -> bool:
    """True when the clip for ``key`` already exists on disk."""
    return cache_path(cache_dir, key, ext).is_file()
