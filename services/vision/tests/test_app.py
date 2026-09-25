from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ctcv_core import get_version
from ctcv_vision import app as app_module
from ctcv_vision.app import SERVICE_NAME, create_app, not_implemented_yet
from ctcv_vision.settings import VisionSettings

PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


def test_health_reports_models_ttl_and_skipped_checks(client: TestClient, settings: VisionSettings):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == SERVICE_NAME
    assert body["version"] == get_version()
    assert body["checks"] == {"ui_detector": "skipped", "vlm": "skipped", "screen_store": "skipped"}
    assert body["models"] == {"ui_detector": settings.detector_model, "vlm": settings.vlm_model}
    assert body["screen_ttl_seconds"] == settings.screen_ttl_seconds


@pytest.mark.parametrize("path", ["/detect", "/screen"])
def test_image_routes_return_501_naming_e08(client: TestClient, path: str):
    response = client.post(path, files={"image": ("man-hinh.png", PNG_HEADER, "image/png")})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED"
    assert "E08" in error["message"]
    assert error["details"] == {"epic": "E08"}
    assert "bác" in error["message"]


@pytest.mark.parametrize("path", ["/detect", "/screen"])
def test_image_routes_without_file_are_vietnamese_422(client: TestClient, path: str):
    response = client.post(path)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert "image" in ".".join(error["details"]["fields"])
    assert "bác" in error["message"]


def test_not_implemented_yet_helper_defaults_to_e08():
    error = not_implemented_yet("Phần đọc màn hình")
    assert error.status == 501
    assert error.details == {"epic": "E08"}
    assert not_implemented_yet("X", epic="E12").details == {"epic": "E12"}


def test_create_app_loads_settings_when_not_given():
    app = create_app()
    assert isinstance(app.state.settings, VisionSettings)


def test_main_runs_uvicorn_on_configured_port(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        app_module.uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw})
    )
    app_module.main()
    assert len(calls) == 1
    assert calls[0]["port"] == VisionSettings.load(env={}).port
    assert calls[0]["app"].title == "CTCV vision"
