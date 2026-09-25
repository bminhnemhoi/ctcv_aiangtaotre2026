"""Container entrypoint: resolve a service's ASGI application and serve it with uvicorn.

Usage (the Dockerfiles' ``CMD``)::

    python /app/serve.py <package> <port> [--host 0.0.0.0] [--reload] [--reload-dir DIR ...]

The E01 brief fixes the *form* ``uvicorn <pkg>.main:app --host 0.0.0.0 --port <port>`` but
the services expose their app in different ways (``ctcv_api.asgi:app``,
``ctcv_speech.app:create_app`` …). This script tries, in order, the first importable
target of ``CANDIDATES`` and hands its import string to uvicorn (``factory=True`` for
``create_app``). ``CTCV_APP_TARGET=module:attr`` (append ``()`` for a factory) overrides the
lookup. Standard library + uvicorn only, so it runs in every ``python:3.12-slim`` image.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from types import ModuleType

TARGET_ENV = "CTCV_APP_TARGET"
FACTORY_SUFFIX = "()"
EXIT_NO_APP = 3
# (submodule, attribute, is_factory) — first importable match wins.
CANDIDATES: tuple[tuple[str, str, bool], ...] = (
    ("main", "app", False),
    ("asgi", "app", False),
    ("app", "app", False),
    ("main", "create_app", True),
    ("app", "create_app", True),
)


@dataclass(frozen=True, slots=True)
class Target:
    """An ASGI import target as uvicorn understands it."""

    module: str
    attr: str
    factory: bool

    @property
    def import_string(self) -> str:
        """``module:attr`` for ``uvicorn.run``."""
        return f"{self.module}:{self.attr}"


def parse_target(spec: str) -> Target:
    """Parse ``module:attr`` or ``module:factory()`` into a :class:`Target`.

    Raises:
        ValueError: when ``spec`` has no ``:`` separator.
    """
    module, sep, attr = spec.strip().partition(":")
    if not sep or not module or not attr:
        raise ValueError(f"{TARGET_ENV} phải có dạng module:attr, nhận được: {spec!r}")
    factory = attr.endswith(FACTORY_SUFFIX)
    return Target(module, attr.removesuffix(FACTORY_SUFFIX), factory)


def _import_optional(module_name: str) -> ModuleType | None:
    """Import ``module_name``; ``None`` when *that* module is absent (other errors propagate)."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name and (module_name == exc.name or module_name.startswith(exc.name + ".")):
            return None
        raise


def resolve_target(package: str, explicit: str | None = None) -> Target:
    """Return the ASGI target for ``package`` (explicit spec first, then ``CANDIDATES``).

    Raises:
        LookupError: when no candidate module exposes the expected attribute.
    """
    if explicit:
        return parse_target(explicit)
    tried: list[str] = []
    for submodule, attr, factory in CANDIDATES:
        module_name = f"{package}.{submodule}"
        tried.append(f"{module_name}:{attr}")
        module = _import_optional(module_name)
        if module is not None and callable(getattr(module, attr, None)):
            return Target(module_name, attr, factory)
    raise LookupError(
        f"Không tìm thấy ứng dụng ASGI trong gói {package} (đã thử: {', '.join(tried)}). "
        f"Dịch vụ này chưa có HTTP server, hoặc đặt {TARGET_ENV}=module:attr."
    )


def build_parser() -> argparse.ArgumentParser:
    """CLI definition (mirrors the uvicorn flags the compose files use)."""
    parser = argparse.ArgumentParser(description="Serve a CTCV service with uvicorn.")
    parser.add_argument("package", help="import package, e.g. ctcv_api")
    parser.add_argument("port", type=int, help="TCP port (config/app.yaml: ports.<svc>)")
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container-internal bind
    parser.add_argument("--reload", action="store_true", help="dev overlay: hot reload")
    parser.add_argument("--reload-dir", action="append", default=[], metavar="DIR")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Resolve the target and block in ``uvicorn.run`` (returns only on failure)."""
    args = build_parser().parse_args(argv)
    try:
        target = resolve_target(args.package, os.environ.get(TARGET_ENV))
    except (LookupError, ValueError, ImportError) as exc:
        print(f"serve.py: {exc}", file=sys.stderr)
        return EXIT_NO_APP
    try:
        import uvicorn
    except ModuleNotFoundError:
        print(f"serve.py: gói uvicorn chưa có trong image của {args.package}", file=sys.stderr)
        return EXIT_NO_APP
    print(f"serve.py: {target.import_string} (factory={target.factory}) → :{args.port}")
    uvicorn.run(
        target.import_string,
        factory=target.factory,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=args.reload_dir or None,
        log_config=None,  # keep the services' JSON logging (ctcv_core.logging)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
