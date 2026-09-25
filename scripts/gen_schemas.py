"""Export JSON Schemas from the Pydantic models owned by sandbox/ and drills/.

``ctcv_sandbox.schema.Scenario`` → ``config/schemas/scenario.schema.json`` and
``ctcv_drills.schema.Drill`` → ``config/schemas/drill.schema.json``. A target whose
module is not importable yet is skipped with a message (exit 0). ``--check`` exits 1
when a generated file is stale (used by CI once the models exist).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
TARGETS: tuple[tuple[str, str, str], ...] = (
    ("ctcv_sandbox.schema", "Scenario", "scenario.schema.json"),
    ("ctcv_drills.schema", "Drill", "drill.schema.json"),
)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def load_model(module: str, attr: str):
    """Import ``module`` and return ``attr`` or ``None`` when unavailable."""
    try:
        return getattr(importlib.import_module(module), attr, None)
    except ImportError:
        return None


def render_schema(model) -> str:
    """Serialise a Pydantic model's JSON Schema deterministically."""
    schema = model.model_json_schema()
    schema.setdefault("$schema", SCHEMA_DIALECT)
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def export_target(module: str, attr: str, out_path: Path, check: bool) -> str:
    """Return ``skipped`` | ``written`` | ``unchanged`` | ``stale`` for one target."""
    model = load_model(module, attr)
    if model is None or not hasattr(model, "model_json_schema"):
        return "skipped"
    text = render_schema(model)
    current = out_path.read_text(encoding="utf-8") if out_path.is_file() else None
    if current == text:
        return "unchanged"
    if check:
        return "stale"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return "written"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--check", action="store_true", help="fail if any schema file is stale")
    args = parser.parse_args(argv)
    stale = 0
    for module, attr, filename in TARGETS:
        out_path = args.root / "config" / "schemas" / filename
        status = export_target(module, attr, out_path, args.check)
        if status == "skipped":
            print(f"BỎ QUA {filename}: chưa import được {module}.{attr} (gói của WP E chưa có).")
        elif status == "stale":
            stale += 1
            print(f"LỖI {filename}: đã cũ so với {module}.{attr} — chạy `make schemas`.")
        else:
            print(f"{status.upper()} {filename} ← {module}.{attr}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
