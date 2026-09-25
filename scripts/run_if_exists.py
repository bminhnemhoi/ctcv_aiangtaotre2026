"""Run a Python module as ``__main__`` if it is importable; otherwise exit 0 with a notice.

`make eval` / `make redteam` call this so that `make check` stays green before the
owning epic lands the module::

    uv run python scripts/run_if_exists.py ctcv_eval.harness --quick

The module's exit code is propagated when it runs.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys

EPIC_HINTS = {
    "ctcv_eval.harness": "E05",
    "ctcv_eval.redteam": "E05",
    "ctcv_eval.loadtest": "E11",
    "ctcv_eval.pilot": "PILOT",
    "ctcv_data.pipeline": "E03",
    "ctcv_training": "E07",
}
DEFAULT_EPIC = "E01"


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _find_spec(module: str):
    try:
        return importlib.util.find_spec(module)
    except (ModuleNotFoundError, ValueError):
        return None


def is_runnable(module: str) -> bool:
    """Return True when ``module`` can run as ``__main__`` (a package needs ``__main__.py``)."""
    spec = _find_spec(module)
    if spec is None:
        return False
    if spec.submodule_search_locations is not None:
        return _find_spec(f"{module}.__main__") is not None
    return True


def not_implemented_message(module: str) -> str:
    """Vietnamese notice printed when the module is absent."""
    epic = EPIC_HINTS.get(module, DEFAULT_EPIC)
    return f"CHƯA HIỆN THỰC — module {module} chưa có (xem epics/{epic}.md); bỏ qua."


def run_module(module: str, args: list[str]) -> int:
    """Execute ``module`` as ``__main__`` with ``args`` and return its exit code."""
    sys.argv = [module, *args]
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Cách dùng: python scripts/run_if_exists.py <module> [tham số...]", file=sys.stderr)
        return 2
    module, rest = args[0], args[1:]
    if not is_runnable(module):
        print(not_implemented_message(module))
        return 0
    return run_module(module, rest)


if __name__ == "__main__":
    sys.exit(main())
