"""Crawl manifest ``data/raw/guides/manifest.jsonl`` — one JSON object per source page.

Fields follow plan §7 step 1 (``url``, ``fetched_at``, ``sha256``, ``license_note``) plus
``agency``, ``source_type``, ``status``, ``content_path`` and ``robots`` so later steps
(normalize, registry) can join on ``url`` without re-reading ``sources.yaml``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ctcv_core.errors import ValidationFailed

MANIFEST_NAME = "manifest.jsonl"
STATUSES: tuple[str, ...] = ("pending", "fetched", "skipped", "error")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(slots=True)
class ManifestEntry:
    """One row of the manifest (a source page and what the crawler knows about it)."""

    url: str
    agency: str
    source_type: str
    license_note: str
    status: str = "pending"
    fetched_at: str | None = None
    sha256: str | None = None
    content_path: str | None = None
    robots: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def validate(self) -> None:
        """Raise ``ValidationFailed`` when a field is out of range."""
        problems: list[str] = []
        if not self.url.startswith(("http://", "https://")):
            problems.append(f"url không phải http(s): {self.url!r}")
        if self.status not in STATUSES:
            problems.append(f"status '{self.status}' không thuộc {STATUSES}")
        if self.sha256 is not None and not _SHA256_RE.match(self.sha256):
            problems.append("sha256 phải là 64 ký tự hex")
        if self.status == "fetched" and (self.sha256 is None or self.fetched_at is None):
            problems.append("bản ghi 'fetched' phải có sha256 và fetched_at")
        if problems:
            raise ValidationFailed(
                "Bản ghi manifest không hợp lệ: " + "; ".join(problems),
                details={"url": self.url, "problems": problems},
            )

    def to_json(self) -> str:
        """Serialise to one JSON line (UTF-8 preserved, keys in field order)."""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> ManifestEntry:
        """Parse one JSON line; unknown keys are rejected so drift is caught early."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationFailed(f"Dòng manifest không phải JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationFailed("Dòng manifest phải là một đối tượng JSON.")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValidationFailed(
                f"Dòng manifest có khóa lạ: {sorted(unknown)}", details={"unknown": sorted(unknown)}
            )
        entry = cls(**data)
        entry.validate()
        return entry


def write_manifest(path: Path, entries: Iterable[ManifestEntry]) -> Path:
    """Write ``entries`` as JSON lines to ``path`` (parent directories are created)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for entry in entries:
        entry.validate()
        lines.append(entry.to_json())
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_manifest(path: Path) -> list[ManifestEntry]:
    """Read every non-blank line of ``path`` as a :class:`ManifestEntry`."""
    if not path.is_file():
        raise ValidationFailed(f"Thiếu manifest: {path}", details={"path": str(path)})
    entries: list[ManifestEntry] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(ManifestEntry.from_json(line))
        except ValidationFailed as exc:
            raise ValidationFailed(f"{path.name} dòng {number}: {exc.message_vi}") from exc
    return entries


def index_by_url(entries: Iterable[ManifestEntry]) -> dict[str, ManifestEntry]:
    """Return ``{url: entry}``; a duplicated url raises ``ValidationFailed``."""
    index: dict[str, ManifestEntry] = {}
    for entry in entries:
        if entry.url in index:
            raise ValidationFailed(f"Manifest có url trùng: {entry.url}")
        index[entry.url] = entry
    return index
