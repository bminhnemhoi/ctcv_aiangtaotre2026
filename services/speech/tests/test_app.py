from __future__ import annotations

import dataclasses

import pytest
from fastapi.testclient import TestClient

from ctcv_core import get_version
from ctcv_speech import app as app_module
from ctcv_speech.app import (
    SERVICE_NAME,
    check_text_length,
    create_app,
    http_error,
    not_implemented_yet,
    validation_message,
)
from ctcv_speech.settings import SpeechSettings

WAV_HEADER = b"RIFF\x00\x00\x00\x00WAVEfmt "


def test_health_reports_models_and_skipped_checks(client: TestClient, settings: SpeechSettings):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == SERVICE_NAME
    assert body["version"] == get_version()
    assert body["checks"] == {
        "asr_model": "skipped",
        "tts_model": "skipped",
        "tts_cache": "skipped",
    }
    assert body["models"] == {
        "asr": settings.asr_model,
        "asr_small": settings.asr_small_model,
        "tts": settings.tts_model,
    }


def test_asr_multipart_returns_501_naming_e04(client: TestClient):
    response = client.post("/asr", files={"audio": ("cau-hoi.wav", WAV_HEADER, "audio/wav")})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED"
    assert "E04" in error["message"]
    assert error["details"] == {"epic": "E04"}
    assert "bác" in error["message"]


def test_asr_without_file_is_a_vietnamese_422(client: TestClient):
    response = client.post("/asr")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert "audio" in ".".join(error["details"]["fields"])
    assert "bác" in error["message"]


def test_tts_returns_501_naming_e04(client: TestClient):
    response = client.post("/tts", json={"text": "Bác bấm nút xanh có chữ Tiếp tục nhé."})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED"
    assert "E04" in error["message"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": ""},
        {"voice": "nam"},
        {"text": "   "},
        {"text": "\n\t "},
        {"text": 12},
        {"text": "xin chào", "otp": "123456"},
        {"text": "xin chào", "voice": 3},
    ],
)
def test_tts_rejects_invalid_body(client: TestClient, payload: dict):
    response = client.post("/tts", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert "bác" in error["message"]


def test_tts_blank_text_explains_in_vietnamese(client: TestClient):
    error = client.post("/tts", json={"text": "   "}).json()["error"]
    assert error["message"] == "Văn bản cần đọc đang trống, bác nhập lại giúp cháu nhé."
    assert error["details"]["fields"] == ["body.text"]


def test_tts_extra_fields_are_rejected_not_ignored(client: TestClient):
    error = client.post("/tts", json={"text": "xin chào", "otp": "123456"}).json()["error"]
    assert "body.otp" in error["details"]["fields"]


def test_tts_text_longer_than_the_limit_is_a_vietnamese_422(settings: SpeechSettings):
    limited = dataclasses.replace(settings, tts_max_text_chars=20)
    with TestClient(create_app(limited)) as client:
        assert client.post("/tts", json={"text": "x" * 20}).status_code == 501
        response = client.post("/tts", json={"text": "x" * 21})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert "20" in error["message"]
    assert "bác" in error["message"]
    assert error["details"] == {"fields": ["body.text"], "max_chars": 20, "chars": 21}


def test_check_text_length_accepts_up_to_the_limit():
    check_text_length("a" * 5, 5)
    with pytest.raises(app_module.ValidationFailed):
        check_text_length("a" * 6, 5)


def test_error_body_has_no_extra_top_level_keys(client: TestClient):
    body = client.post("/tts", json={"text": "xin chào"}).json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}


def test_unknown_route_uses_the_unified_error_body(client: TestClient):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Không tìm thấy nội dung này, bác thử chọn mục khác nhé.",
        }
    }


def test_wrong_method_uses_the_unified_error_body_and_keeps_allow(client: TestClient):
    response = client.get("/asr")
    assert response.status_code == 405
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "bác" in body["error"]["message"]
    assert "POST" in response.headers["allow"]


def test_http_error_helper_maps_statuses():
    assert http_error(404).code == "NOT_FOUND"
    assert http_error(405).code == "METHOD_NOT_ALLOWED"
    generic = http_error(418)
    assert (generic.code, generic.status) == ("HTTP_418", 418)
    assert "bác" in generic.message_vi


def test_validation_message_prefers_custom_validator_text():
    errors = [
        {"type": "missing", "loc": ("body", "x")},
        {"type": "value_error", "loc": ("body", "text"), "ctx": {"error": ValueError("Trống")}},
    ]
    assert validation_message(errors) == "Trống"
    assert validation_message([{"type": "missing", "loc": ("body", "x")}]) is None
    assert validation_message([{"type": "value_error", "ctx": {"error": ValueError("")}}]) is None


def test_not_implemented_yet_helper_defaults_to_e04():
    error = not_implemented_yet("Phần nghe")
    assert error.status == 501
    assert error.code == "NOT_IMPLEMENTED"
    assert error.details == {"epic": "E04"}
    assert not_implemented_yet("X", epic="E08").details == {"epic": "E08"}


def test_create_app_loads_settings_when_not_given():
    app = create_app()
    assert isinstance(app.state.settings, SpeechSettings)


def test_main_runs_uvicorn_on_configured_port(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        app_module.uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw})
    )
    app_module.main()
    assert len(calls) == 1
    assert calls[0]["port"] == SpeechSettings.load(env={}).port
    assert calls[0]["app"].title == "CTCV speech"
