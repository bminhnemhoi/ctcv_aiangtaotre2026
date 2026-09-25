"""Manifest JSONL writer/reader round-trip and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctcv_core.errors import ValidationFailed
from ctcv_data.manifest import ManifestEntry, index_by_url, read_manifest, write_manifest


def _entry(**overrides: object) -> ManifestEntry:
    base = {
        "url": "https://dichvucong.gov.vn/p/home",
        "agency": "Cổng DVC",
        "source_type": "co_quan_nha_nuoc",
        "license_note": "chỉ trích dẫn",
    }
    return ManifestEntry(**{**base, **overrides})  # type: ignore[arg-type]


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    entries = [
        _entry(),
        _entry(
            url="https://vneid.gov.vn/huong-dan",
            status="fetched",
            fetched_at="2026-09-18T01:02:03+00:00",
            sha256="a" * 64,
            content_path="data/raw/guides/vneid-huong-dan.html",
            robots={"fetched": True, "allowed": True},
            notes="ghi chú tiếng Việt",
        ),
    ]
    path = write_manifest(tmp_path / "guides" / "manifest.jsonl", entries)
    assert path.is_file()
    assert read_manifest(path) == entries
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert "ghi chú tiếng Việt" in path.read_text(encoding="utf-8")  # ensure_ascii=False


def test_empty_manifest(tmp_path: Path) -> None:
    path = write_manifest(tmp_path / "manifest.jsonl", [])
    assert read_manifest(path) == []


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed, match="Thiếu manifest"):
        read_manifest(tmp_path / "nope.jsonl")


@pytest.mark.parametrize(
    "overrides",
    [
        {"url": "ftp://x"},
        {"status": "done"},
        {"sha256": "xyz"},
        {"status": "fetched"},  # fetched needs sha256 + fetched_at
    ],
)
def test_invalid_entries_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationFailed):
        _entry(**overrides).validate()


def test_unknown_keys_and_bad_lines_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    path.write_text(
        '{"url": "https://a.gov.vn/", "agency": "", "source_type": "", '
        '"license_note": "", "extra": 1}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationFailed, match="dòng 1"):
        read_manifest(path)
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValidationFailed, match="dòng 1"):
        read_manifest(path)


def test_index_by_url_rejects_duplicates() -> None:
    assert list(index_by_url([_entry()])) == ["https://dichvucong.gov.vn/p/home"]
    with pytest.raises(ValidationFailed, match="trùng"):
        index_by_url([_entry(), _entry()])
