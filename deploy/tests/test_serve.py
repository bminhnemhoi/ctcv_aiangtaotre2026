"""Tests for deploy/docker/serve.py — ASGI target resolution without starting uvicorn."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SERVE_PATH = Path(__file__).resolve().parents[1] / "docker" / "serve.py"
ASGI_APP = "async def app(scope, receive, send):\n    pass\n"
FACTORY = "def create_app():\n    return object()\n"


@pytest.fixture(scope="module")
def serve() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ctcv_serve", SERVE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve `from __future__` annotations via it
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in [n for n in sys.modules if n.startswith("fake_")]:
        sys.modules.pop(name)


def _make_package(root: Path, name: str, files: dict[str, str]) -> None:
    pkg = root / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for filename, body in files.items():
        (pkg / filename).write_text(body, encoding="utf-8")


def test_prefers_main_app_over_other_candidates(serve: ModuleType, site: Path) -> None:
    _make_package(site, "fake_main", {"main.py": ASGI_APP, "asgi.py": ASGI_APP})
    target = serve.resolve_target("fake_main")
    assert target.import_string == "fake_main.main:app" and target.factory is False


def test_falls_back_to_asgi_app(serve: ModuleType, site: Path) -> None:
    _make_package(site, "fake_asgi", {"asgi.py": ASGI_APP, "app.py": FACTORY})
    assert serve.resolve_target("fake_asgi").import_string == "fake_asgi.asgi:app"


def test_factory_in_app_module(serve: ModuleType, site: Path) -> None:
    _make_package(site, "fake_factory", {"app.py": FACTORY})
    target = serve.resolve_target("fake_factory")
    assert target.import_string == "fake_factory.app:create_app" and target.factory is True


def test_non_callable_attribute_is_ignored(serve: ModuleType, site: Path) -> None:
    _make_package(site, "fake_value", {"main.py": "app = 'not an app'\n", "app.py": FACTORY})
    assert serve.resolve_target("fake_value").import_string == "fake_value.app:create_app"


def test_missing_package_raises_lookup_error(serve: ModuleType, site: Path) -> None:
    with pytest.raises(LookupError, match="fake_absent"):
        serve.resolve_target("fake_absent")


def test_broken_dependency_is_not_swallowed(serve: ModuleType, site: Path) -> None:
    _make_package(site, "fake_broken", {"main.py": "import fake_missing_dependency_xyz\n"})
    with pytest.raises(ModuleNotFoundError, match="fake_missing_dependency_xyz"):
        serve.resolve_target("fake_broken")


def test_explicit_target_overrides_lookup(serve: ModuleType) -> None:
    target = serve.resolve_target("ignored", "ctcv_api.main:create_app()")
    assert target == serve.Target("ctcv_api.main", "create_app", True)
    assert serve.parse_target("ctcv_api.asgi:app").factory is False
    with pytest.raises(ValueError, match="module:attr"):
        serve.parse_target("nonsense")


def test_main_reports_missing_app_in_vietnamese(
    serve: ModuleType, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert serve.main(["fake_absent", "8010"]) == serve.EXIT_NO_APP
    assert "Không tìm thấy ứng dụng ASGI" in capsys.readouterr().err


def test_main_hands_target_to_uvicorn(
    serve: ModuleType, site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_package(site, "fake_speech", {"app.py": FACTORY})
    calls: list[tuple[str, dict]] = []
    fake_uvicorn = SimpleNamespace(run=lambda target, **kw: calls.append((target, kw)))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    rc = serve.main(["fake_speech", "8020", "--reload", "--reload-dir", "/app/x"])
    assert rc == 0 and calls == [
        (
            "fake_speech.app:create_app",
            {
                "factory": True,
                "host": "0.0.0.0",
                "port": 8020,
                "reload": True,
                "reload_dirs": ["/app/x"],
                "log_config": None,
            },
        )
    ]
