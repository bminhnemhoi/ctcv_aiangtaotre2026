"""Contract tests for the 17 routes of brief §3 + ADR-007 C6 (status, bodies, auth, roles).

``POST /v1/coach/ask`` is implemented since ADR-007, so it left ``STUBS``; its 401/403
checks live in ``test_coach_ask.py`` and ``POST /v1/coach/intake-check`` in
``test_intake_check.py``. ``/v1/auth/join`` and ``/v1/auth/login`` stay stubs here because
the test settings never enable the demo mode.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from ctcv_api.auth import create_token
from ctcv_api.main import create_app
from ctcv_api.schemas import ScenarioSummary

UUID = str(uuid.uuid4())
ALL_ROLES = ("citizen", "volunteer", "officer")
WAV = {"audio": ("clip.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")}
PNG = {"image": ("screen.png", b"\x89PNG\r\n\x1a\n", "image/png")}

# (method, path, roles allowed (None = public), json body, multipart files, epic)
STUBS = [
    (
        "POST",
        "/v1/auth/join",
        None,
        {"qr_token": "abcdefghij", "display_name": "HV01"},
        None,
        "E10",
    ),
    ("POST", "/v1/auth/login", None, {"username": "tnv01", "password": "secret"}, None, "E10"),
    ("POST", "/v1/classes", ("volunteer",), {"name": "Lớp 1", "ward_code": "79001"}, None, "E10"),
    ("GET", f"/v1/classes/{UUID}/progress", ("volunteer", "officer"), None, None, "E10"),
    ("GET", f"/v1/reports/class/{UUID}?format=pdf", ("volunteer", "officer"), None, None, "E10"),
    ("POST", "/v1/sessions", ("citizen",), {"scenario_id": "chuyen-khoan-qr"}, None, "E02"),
    ("POST", "/v1/speech/asr", ALL_ROLES, None, WAV, "E04"),
    ("POST", "/v1/speech/tts", ALL_ROLES, {"text": "Bác bấm nút xanh nhé."}, None, "E04"),
    ("POST", "/v1/coach/screen", ("citizen", "volunteer"), None, PNG, "E08"),
    ("POST", "/v1/drills", ("citizen",), {}, None, "E09"),
    ("POST", f"/v1/drills/{UUID}/answers", ("citizen",), {"option_id": "a"}, None, "E09"),
]
PROTECTED = [stub for stub in STUBS if stub[2]]
ROLE_RESTRICTED = [stub for stub in STUBS if stub[2] and set(stub[2]) != set(ALL_ROLES)]

EXPECTED_OPENAPI_PATHS = {
    "/v1/auth/join",
    "/v1/auth/login",
    "/v1/classes",
    "/v1/classes/{class_id}/progress",
    "/v1/reports/class/{class_id}",
    "/v1/scenarios",
    "/v1/sessions",
    "/v1/sessions/{session_id}/events",
    "/v1/speech/asr",
    "/v1/speech/tts",
    "/v1/coach/ask",
    "/v1/coach/intake-check",
    "/v1/coach/screen",
    "/v1/drills",
    "/v1/drills/{drill_id}/answers",
    "/v1/health",
    "/v1/metrics",
}


def _ids(stubs: list[tuple]) -> list[str]:
    return [f"{stub[0]} {stub[1].split('?')[0]}" for stub in stubs]


def _assert_error_shape(body: dict, code: str) -> dict:
    assert set(body) == {"error"}
    error = body["error"]
    assert {"code", "message"} <= set(error)
    assert error["code"] == code
    assert any(ord(ch) > 127 for ch in error["message"]), "message must be Vietnamese"
    return error


@pytest.mark.parametrize(
    ("method", "path", "roles", "body", "files", "epic"), STUBS, ids=_ids(STUBS)
)
def test_stub_returns_501_naming_its_epic(
    client, auth_headers, method, path, roles, body, files, epic
):
    headers = auth_headers(roles[0]) if roles else None
    response = client.request(method, path, headers=headers, json=body, files=files)
    assert response.status_code == 501
    error = _assert_error_shape(response.json(), "NOT_IMPLEMENTED")
    assert epic in error["message"]
    assert error["details"] == {"epic": epic}


@pytest.mark.parametrize(
    ("method", "path", "roles", "body", "files", "epic"), PROTECTED, ids=_ids(PROTECTED)
)
def test_protected_route_requires_token(client, method, path, roles, body, files, epic):
    response = client.request(method, path, json=body, files=files)
    assert response.status_code == 401
    _assert_error_shape(response.json(), "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("method", "path", "roles", "body", "files", "epic"), ROLE_RESTRICTED, ids=_ids(ROLE_RESTRICTED)
)
def test_wrong_role_is_forbidden(client, auth_headers, method, path, roles, body, files, epic):
    for role in ALL_ROLES:
        if role in roles:
            continue
        response = client.request(method, path, headers=auth_headers(role), json=body, files=files)
        assert response.status_code == 403, role
        error = _assert_error_shape(response.json(), "FORBIDDEN")
        assert error["details"]["required"] == sorted(roles)


def test_every_allowed_role_reaches_the_stub(client, auth_headers):
    for method, path, roles, body, files, _epic in PROTECTED:
        for role in roles:
            response = client.request(
                method, path, headers=auth_headers(role), json=body, files=files
            )
            assert response.status_code == 501, (path, role)


def test_invalid_body_is_422_and_never_echoes_input(client, auth_headers):
    response = client.post(
        "/v1/classes", headers=auth_headers("volunteer"), json={"name": "", "ward_code": "79001"}
    )
    assert response.status_code == 422
    error = _assert_error_shape(response.json(), "VALIDATION_FAILED")
    assert error["details"]["errors"]
    for item in error["details"]["errors"]:
        assert set(item) == {"loc", "msg", "type"}


def test_unknown_body_keys_are_rejected(client, auth_headers):
    response = client.post(
        "/v1/coach/ask", headers=auth_headers("citizen"), json={"question": "x", "hack": 1}
    )
    assert response.status_code == 422


def test_display_name_longer_than_32_is_rejected(client):
    body = {"qr_token": "abcdefghij", "display_name": "x" * 33}
    assert client.post("/v1/auth/join", json=body).status_code == 422


@pytest.mark.parametrize("query", ["", "?format=csv", "?format=PDF"])
def test_report_format_must_be_pdf_or_xlsx(client, auth_headers, query):
    response = client.get(f"/v1/reports/class/{UUID}{query}", headers=auth_headers("officer"))
    assert response.status_code == 422


def test_report_accepts_xlsx(client, auth_headers):
    response = client.get(f"/v1/reports/class/{UUID}?format=xlsx", headers=auth_headers("officer"))
    assert response.status_code == 501


def test_bad_uuid_path_param_is_422(client, auth_headers):
    response = client.get("/v1/classes/not-a-uuid/progress", headers=auth_headers("officer"))
    assert response.status_code == 422


def test_asr_requires_multipart_audio(client, auth_headers):
    response = client.post("/v1/speech/asr", headers=auth_headers("citizen"), json={"audio": "x"})
    assert response.status_code == 422


# ---------------------------------------------------------------- scenarios (real)
def test_scenarios_returns_fixture_scenarios(client, auth_headers):
    response = client.get("/v1/scenarios", headers=auth_headers("citizen"))
    assert response.status_code == 200
    items = [ScenarioSummary.model_validate(item) for item in response.json()]
    assert [item.id for item in items] == ["chuyen-khoan-qr", "dang-nhap-vneid"]
    first = items[0]
    assert (first.skill_group, first.level, first.version) == ("thanh-toan-thue-so", 1, "1.0.0")
    assert first.goal.startswith("Chuyển 200.000đ")


def test_scenarios_serves_the_real_sandbox_sample(settings_factory):
    """Brief §15: with no directory override the E01 sample scenario from sandbox/ is listed."""
    app = create_app(settings_factory(scenarios_dir=None))
    token = create_token("u-1", "citizen", app.state.settings)
    with TestClient(app) as real_client:
        response = real_client.get("/v1/scenarios", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    items = [ScenarioSummary.model_validate(item) for item in response.json()]
    assert "chuyen-khoan-qr" in [item.id for item in items]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_scenarios_open_to_every_role(client, auth_headers, role):
    assert client.get("/v1/scenarios", headers=auth_headers(role)).status_code == 200


def test_scenarios_requires_token(client):
    response = client.get("/v1/scenarios")
    assert response.status_code == 401
    _assert_error_shape(response.json(), "UNAUTHORIZED")


def test_scenarios_filter_by_skill(client, auth_headers):
    response = client.get(
        "/v1/scenarios", params={"skill": "dinh-danh-vneid"}, headers=auth_headers("citizen")
    )
    assert [item["id"] for item in response.json()] == ["dang-nhap-vneid"]


def test_scenarios_filter_by_level(client, auth_headers):
    response = client.get("/v1/scenarios", params={"level": 1}, headers=auth_headers("citizen"))
    assert [item["id"] for item in response.json()] == ["chuyen-khoan-qr"]


def test_scenarios_filter_by_skill_and_level_can_be_empty(client, auth_headers):
    response = client.get(
        "/v1/scenarios",
        params={"skill": "dinh-danh-vneid", "level": 1},
        headers=auth_headers("citizen"),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_scenarios_unknown_skill_is_422(client, auth_headers):
    response = client.get(
        "/v1/scenarios", params={"skill": "hack"}, headers=auth_headers("citizen")
    )
    assert response.status_code == 422
    error = _assert_error_shape(response.json(), "SKILL_INVALID")
    assert "thanh-toan-thue-so" in error["details"]["allowed"]


@pytest.mark.parametrize("level", [0, 4, "abc"])
def test_scenarios_level_out_of_range_is_422(client, auth_headers, level):
    response = client.get("/v1/scenarios", params={"level": level}, headers=auth_headers("citizen"))
    assert response.status_code == 422
    _assert_error_shape(response.json(), "VALIDATION_FAILED")


# ---------------------------------------------------------------- sessions events (SSE)
def test_session_events_is_sse_with_single_not_implemented_event(client, auth_headers):
    response = client.post(
        f"/v1/sessions/{UUID}/events",
        headers=auth_headers("citizen"),
        json={"type": "tap", "target": "btn_qr"},
    )
    assert response.status_code == 501
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [frame for frame in response.text.split("\n\n") if frame.strip()]
    assert len(frames) == 1
    assert "event: error" in frames[0]
    assert '"NOT_IMPLEMENTED"' in frames[0]
    assert "E02" in frames[0]


def test_session_events_validates_body_before_streaming(client, auth_headers):
    response = client.post(
        f"/v1/sessions/{UUID}/events", headers=auth_headers("citizen"), json={"type": "swipe"}
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("role", ["volunteer", "officer"])
def test_session_events_is_citizen_only(client, auth_headers, role):
    response = client.post(
        f"/v1/sessions/{UUID}/events", headers=auth_headers(role), json={"type": "back"}
    )
    assert response.status_code == 403


def test_session_events_requires_token(client):
    response = client.post(f"/v1/sessions/{UUID}/events", json={"type": "back"})
    assert response.status_code == 401


# ---------------------------------------------------------------- surface
def test_no_endpoint_lists_all_drills(client, auth_headers):
    response = client.get("/v1/drills", headers=auth_headers("citizen"))
    assert response.status_code == 405
    _assert_error_shape(response.json(), "METHOD_NOT_ALLOWED")
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" not in paths["/v1/drills"]


def test_openapi_lists_exactly_the_contract_paths(client: TestClient):
    paths = client.get("/openapi.json").json()["paths"]
    assert len(EXPECTED_OPENAPI_PATHS) == 17  # 16 of brief §3 + intake-check (ADR-007 C6)
    assert set(paths) == EXPECTED_OPENAPI_PATHS


def test_root_health_and_metrics_aliases_exist_but_are_hidden(client: TestClient):
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" not in paths and "/metrics" not in paths


def test_openapi_documents_bearer_auth(client: TestClient):
    spec = client.get("/openapi.json").json()
    assert "HTTPBearer" in spec["components"]["securitySchemes"]
    assert spec["paths"]["/v1/scenarios"]["get"]["security"]
