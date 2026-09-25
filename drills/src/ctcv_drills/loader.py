"""Load drills from ``drills/scenarios/*.json`` and compute their checksum.

File naming: ``<key>.json`` is variant 1, ``<key>.v<n>.json`` is variant ``n``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ctcv_core.errors import NotFound, ValidationFailed
from ctcv_core.paths import DRILLS_DIR
from ctcv_drills.schema import Drill

DRILL_NOT_FOUND = "DRILL_NOT_FOUND"
DRILL_INVALID = "DRILL_INVALID"
NOT_FOUND_MESSAGE = "Không tìm thấy bài luyện này, bác thử bài khác nhé."
INVALID_MESSAGE = "Bài luyện này đang lỗi, bác thử bài khác nhé."


def file_name(key: str, variant: int = 1) -> str:
    """Return the file name that holds ``key`` variant ``variant``."""
    return f"{key}.json" if variant == 1 else f"{key}.v{variant}.json"


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file; raise ``ValidationFailed`` (DRILL_INVALID) on bad JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationFailed(
            INVALID_MESSAGE, code=DRILL_INVALID, details={"path": path.name, "error": str(exc)}
        ) from exc


def parse_drill(data: Mapping[str, Any], source: str = "") -> Drill:
    """Build a :class:`Drill`; raise ``ValidationFailed`` (DRILL_INVALID) on schema errors."""
    try:
        return Drill.model_validate(data)
    except ValidationError as exc:
        raise ValidationFailed(
            INVALID_MESSAGE,
            code=DRILL_INVALID,
            details={"source": source, "errors": [e["msg"] for e in exc.errors()]},
        ) from exc


def drill_files(dir: Path = DRILLS_DIR) -> list[Path]:
    """Return every ``*.json`` file in ``dir`` sorted by name."""
    return sorted(p for p in dir.glob("*.json") if p.is_file())


def list_drills(dir: Path = DRILLS_DIR) -> list[Drill]:
    """Load every drill in ``dir`` sorted by ``(key, variant)`` (schema-validated only)."""
    drills = [parse_drill(read_json(path), path.name) for path in drill_files(dir)]
    return sorted(drills, key=lambda d: (d.key, d.variant))


def load_drill(key: str, variant: int = 1, dir: Path = DRILLS_DIR) -> Drill:
    """Load one variant of ``key``; raise ``NotFound`` (DRILL_NOT_FOUND) if absent."""
    path = dir / file_name(key, variant)
    if not path.is_file():
        raise NotFound(
            NOT_FOUND_MESSAGE, code=DRILL_NOT_FOUND, details={"key": key, "variant": variant}
        )
    drill = parse_drill(read_json(path), path.name)
    if drill.key != key or drill.variant != variant:
        raise ValidationFailed(
            INVALID_MESSAGE,
            code=DRILL_INVALID,
            details={"key": key, "variant": variant, "file_key": drill.key},
        )
    return drill


def variants_of(key: str, dir: Path = DRILLS_DIR) -> list[Drill]:
    """Every variant of ``key`` present in ``dir``, sorted by variant (may be empty)."""
    return [d for d in list_drills(dir) if d.key == key]


def canonical_json(drill: Drill) -> str:
    """Serialise deterministically (sorted keys, compact separators, UTF-8 preserved)."""
    payload = drill.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(drill: Drill) -> str:
    """SHA-256 hex digest of the canonical JSON."""
    return hashlib.sha256(canonical_json(drill).encode("utf-8")).hexdigest()
