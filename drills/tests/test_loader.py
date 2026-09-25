from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ctcv_core.errors import NotFound, ValidationFailed
from ctcv_core.paths import DRILLS_DIR
from ctcv_drills.loader import (
    DRILL_INVALID,
    DRILL_NOT_FOUND,
    canonical_json,
    checksum,
    drill_files,
    file_name,
    list_drills,
    load_drill,
    variants_of,
)
from ctcv_drills.schema import Drill

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_KEY = "gia-danh-cong-an-goi-dien"
SAMPLE_PATH = DRILLS_DIR / f"{SAMPLE_KEY}.json"
WriteJson = Callable[[Path, Any], Path]


def test_default_dir_lists_the_sample() -> None:
    keys = [(d.key, d.variant) for d in list_drills()]
    assert (SAMPLE_KEY, 1) in keys and keys == sorted(keys)


def test_file_name() -> None:
    assert file_name("k") == "k.json" and file_name("k", 4) == "k.v4.json"


def test_drill_files_ignores_non_json(drills_dir: Path) -> None:
    assert [p.name for p in drill_files(drills_dir)] == [f"{SAMPLE_KEY}.json"]


def test_load_drill_and_variants(
    drills_dir: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    sample_dict["variant"] = 2
    write_json(drills_dir / f"{SAMPLE_KEY}.v2.json", sample_dict)
    assert load_drill(SAMPLE_KEY, dir=drills_dir).variant == 1
    assert load_drill(SAMPLE_KEY, 2, drills_dir).variant == 2
    assert [d.variant for d in variants_of(SAMPLE_KEY, drills_dir)] == [1, 2]
    assert variants_of("khong-co", drills_dir) == []


def test_load_drill_not_found(drills_dir: Path) -> None:
    with pytest.raises(NotFound) as exc:
        load_drill(SAMPLE_KEY, 3, drills_dir)
    assert exc.value.code == DRILL_NOT_FOUND and exc.value.status == 404
    assert exc.value.details == {"key": SAMPLE_KEY, "variant": 3}


def test_load_drill_bad_json(drills_dir: Path) -> None:
    (drills_dir / "hong.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValidationFailed) as exc:
        load_drill("hong", dir=drills_dir)
    assert exc.value.code == DRILL_INVALID


def test_load_drill_schema_error(
    drills_dir: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    sample_dict["key"] = "sai-schema"
    sample_dict["severity"] = 9
    write_json(drills_dir / "sai-schema.json", sample_dict)
    with pytest.raises(ValidationFailed) as exc:
        load_drill("sai-schema", dir=drills_dir)
    assert exc.value.code == DRILL_INVALID
    assert exc.value.details is not None and exc.value.details["errors"]


def test_load_drill_key_mismatch(
    drills_dir: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    write_json(drills_dir / "ten-khac.json", sample_dict)
    with pytest.raises(ValidationFailed) as exc:
        load_drill("ten-khac", dir=drills_dir)
    assert exc.value.details is not None and exc.value.details["file_key"] == SAMPLE_KEY


def test_checksum_is_stable_and_sensitive(sample: Drill, sample_dict: dict[str, Any]) -> None:
    digest = checksum(sample)
    assert len(digest) == 64 and checksum(Drill.model_validate(sample_dict)) == digest
    sample_dict["severity"] = 1
    assert checksum(Drill.model_validate(sample_dict)) != digest


def test_canonical_json(sample: Drill) -> None:
    text = canonical_json(sample)
    compact = json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert text == compact and text.startswith('{"channel":')
    assert "Mô phỏng" in text
