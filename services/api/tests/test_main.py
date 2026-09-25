"""Entry points: console script, ASGI module, lifespan, version and stub helper."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from ctcv_api import __version__, get_version
from ctcv_api.errors import EPIC_FEATURES, not_implemented
from ctcv_api.main import create_app, run


def test_version_is_a_semver_string():
    assert get_version().count(".") == 2
    assert __version__.count(".") == 2


def test_run_serves_factory_on_configured_port(monkeypatch, settings_factory):
    captured: dict = {}
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: captured.update(kwargs, app=args[0]))
    monkeypatch.setattr("ctcv_api.main.get_settings", lambda: settings_factory(api_port=8123))
    run()
    assert captured["app"] == "ctcv_api.main:create_app"
    assert captured["factory"] is True
    assert captured["port"] == 8123
    assert captured["log_config"] is None


def test_asgi_module_exposes_app(monkeypatch, settings_factory):
    monkeypatch.setattr("ctcv_api.main.get_settings", lambda: settings_factory())
    module = importlib.import_module("ctcv_api.asgi")
    module = importlib.reload(module)
    with TestClient(module.app) as client:
        assert client.get("/health").status_code == 200


def test_create_app_without_settings_uses_environment(monkeypatch, settings_factory):
    monkeypatch.setattr("ctcv_api.main.get_settings", lambda: settings_factory(jwt_ttl_minutes=9))
    app = create_app()
    assert app.state.settings.jwt_ttl_minutes == 9


def test_lifespan_disposes_engine(app, monkeypatch):
    disposed: list[bool] = []
    monkeypatch.setattr(app.state.engine, "dispose", lambda: disposed.append(True))
    with TestClient(app):
        pass
    assert disposed == [True]


def test_not_implemented_helper_names_epic_in_vietnamese():
    for epic, feature in EPIC_FEATURES.items():
        error = not_implemented(epic)
        assert error.status == 501 and error.code == "NOT_IMPLEMENTED"
        assert epic in error.message_vi and feature in error.message_vi
        assert error.details == {"epic": epic}
    assert "E99" in not_implemented("E99").message_vi
