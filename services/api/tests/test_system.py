"""Health, metrics, request-id, CORS and the unified error handlers."""

from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ctcv_api import get_version
from ctcv_api.main import create_app
from ctcv_api.metrics import UNMATCHED_PATH, route_template
from ctcv_api.middleware import REQUEST_ID_HEADER
from ctcv_api.schemas import HealthOut
from ctcv_core.errors import NotFound


def test_health_ok_with_skipped_checks(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = HealthOut.model_validate(response.json())
    assert body.status == "ok"
    assert body.version == get_version()
    assert body.checks == {"db": "ok", "redis": "skipped", "qdrant": "skipped"}


def test_health_v1_alias(client: TestClient):
    assert client.get("/v1/health").json()["status"] == "ok"


def test_health_degraded_when_db_unreachable(settings_factory, tmp_path):
    missing = tmp_path / "no-such-dir" / "x.db"
    app = create_app(settings_factory(database_url=f"sqlite+pysqlite:///{missing.as_posix()}"))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"] == "error"


def test_metrics_exposes_http_requests_total(client: TestClient):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "# TYPE http_requests_total counter" in text
    assert 'http_requests_total{method="GET",path="/health",status="200"}' in text
    assert "http_request_duration_seconds" in text


def test_metrics_uses_route_template_not_raw_path(client: TestClient, auth_headers):
    client.get(
        "/v1/classes/00000000-0000-0000-0000-000000000000/progress", headers=auth_headers("officer")
    )
    text = client.get("/v1/metrics").text
    assert 'path="/v1/classes/{class_id}/progress",status="501"' in text
    assert "00000000-0000" not in text


def test_metrics_counts_unmatched_paths_without_leaking_them(client: TestClient):
    client.get("/nope/secret-123")
    text = client.get("/metrics").text
    assert 'path="unmatched",status="404"' in text
    assert "secret-123" not in text


def test_metrics_registry_is_per_app(settings):
    first, second = create_app(settings), create_app(settings)
    with TestClient(first) as one:
        one.get("/health")
        assert "http_requests_total{" in one.get("/metrics").text
    with TestClient(second) as two:
        assert 'path="/health"' not in two.get("/metrics").text


def test_request_id_is_generated(client: TestClient):
    response = client.get("/health")
    request_id = response.headers[REQUEST_ID_HEADER]
    assert len(request_id) == 32


def test_request_id_is_echoed_when_well_formed(client: TestClient):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "abc-123.X"})
    assert response.headers[REQUEST_ID_HEADER] == "abc-123.X"


def test_request_id_is_replaced_when_malformed(client: TestClient):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "bad id with spaces"})
    assert response.headers[REQUEST_ID_HEADER] != "bad id with spaces"


def test_unknown_path_uses_unified_error_body(client: TestClient):
    response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_app_error_is_mapped_to_its_status_and_body(app: FastAPI):
    def boom() -> None:
        raise NotFound(
            "Không tìm thấy bài học này, bác thử chọn bài khác nhé.", code="SCENARIO_NOT_FOUND"
        )

    app.add_api_route("/boom", boom)
    with TestClient(app) as client:
        response = client.get("/boom")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "SCENARIO_NOT_FOUND",
            "message": "Không tìm thấy bài học này, bác thử chọn bài khác nhé.",
        }
    }


def test_unexpected_exception_becomes_500_internal_error(app: FastAPI):
    def crash() -> None:
        raise RuntimeError("secret detail must not leak")

    app.add_api_route("/crash", crash)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret detail" not in response.text
    assert 'status="500"' in client.get("/metrics").text


def test_cors_preflight_allows_dev_web_origin(client: TestClient, settings):
    origin = settings.cors_origin_list[0]
    response = client.options(
        "/v1/scenarios",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_unknown_origin(client: TestClient):
    response = client.options(
        "/v1/scenarios",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def _fake_route(path_format: str, pattern: str) -> SimpleNamespace:
    return SimpleNamespace(
        path_format=path_format, path=path_format, path_regex=re.compile(pattern)
    )


def test_route_template_recovers_router_prefix():
    route = _fake_route("/classes/{class_id}/progress", r"^/classes/(?P<class_id>[^/]+)/progress$")
    scope = {"path": "/v1/classes/abc/progress", "root_path": "", "route": route}
    assert route_template(scope) == "/v1/classes/{class_id}/progress"


def test_route_template_strips_root_path_and_handles_root_alias():
    route = _fake_route("/health", r"^/health$")
    assert route_template({"path": "/api/health", "root_path": "/api", "route": route}) == "/health"
    assert route_template({"path": "/health", "root_path": "", "route": route}) == "/health"


def test_route_template_unmatched_without_route():
    assert route_template({"path": "/nope"}) == UNMATCHED_PATH
