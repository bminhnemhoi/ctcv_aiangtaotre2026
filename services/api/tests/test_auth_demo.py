"""Demo mode of ``/v1/auth/join`` and ``/v1/auth/login`` (ADR-007 C6, C10).

Off by default (501 as in E01), refused in ``prod``, secrets compared in constant time and
never logged or echoed.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ctcv_agent.rag.settings import load_rag_settings
from ctcv_api.auth import decode_token
from ctcv_api.enums import Role
from ctcv_api.main import create_app
from ctcv_api.routers import auth as auth_router
from ctcv_api.settings import Settings

JOIN = "/v1/auth/join"
LOGIN = "/v1/auth/login"
QR_TOKEN = "demo-qr-token-0123456789abcdef"
STAFF_PASSWORD = "demo-staff-pass-9876"
REAL_JWT = "a-real-32-char-secret-value-for-prod"
INVALID_CREDENTIALS = "Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé."


@pytest.fixture
def demo_settings(settings_factory) -> Settings:
    return settings_factory(ctcv_demo_qr_token=QR_TOKEN, ctcv_demo_staff_password=STAFF_PASSWORD)


@pytest.fixture
def demo_client(demo_settings):
    with TestClient(create_app(demo_settings)) as test_client:
        yield test_client


@pytest.fixture
def staff_username() -> str:
    return load_rag_settings().demo_staff_username


def _expected_citizen_id(display_name: str) -> str:
    return "demo-citizen-" + hashlib.sha256(display_name.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- join
def test_demo_join_issues_a_citizen_token(demo_client, demo_settings):
    body = {"qr_token": QR_TOKEN, "display_name": "Học viên"}
    response = demo_client.post(JOIN, json=body)
    assert response.status_code == 200
    out = response.json()
    assert out["user_id"] == _expected_citizen_id("Học viên")
    assert out["role"] == "citizen"
    principal = decode_token(out["token"], demo_settings)
    assert (principal.user_id, principal.role) == (out["user_id"], Role.CITIZEN)


def test_demo_join_id_is_stable_per_nickname(demo_client):
    first = demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"}).json()
    again = demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"}).json()
    other = demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV02"}).json()
    assert first["user_id"] == again["user_id"] != other["user_id"]
    assert "HV01" not in first["user_id"]


@pytest.mark.parametrize(
    "qr_token",
    [QR_TOKEN[:-1] + "X", QR_TOKEN + "x", "abcdefghij", "mã-có-dấu-tiếng-việt-123"],
    ids=["last-char", "longer", "unrelated", "non-ascii"],
)
def test_demo_join_with_a_wrong_token_stays_501(demo_client, qr_token):
    response = demo_client.post(JOIN, json={"qr_token": qr_token, "display_name": "HV01"})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED" and error["details"] == {"epic": "E10"}


def test_join_is_501_when_demo_is_off(client):
    response = client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"})
    assert response.status_code == 501
    assert response.json()["error"]["details"] == {"epic": "E10"}


def test_demo_join_compares_in_constant_time(demo_client, monkeypatch):
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def _spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(auth_router.hmac, "compare_digest", _spy)
    demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"})
    assert calls and all(isinstance(a, bytes) and isinstance(b, bytes) for a, b in calls)


def test_demo_join_token_opens_the_citizen_routes(demo_client):
    token = demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"}).json()
    headers = {"Authorization": f"Bearer {token['token']}"}
    assert demo_client.get("/v1/scenarios", headers=headers).status_code == 200


# ---------------------------------------------------------------- login
def test_demo_login_issues_an_officer_token(demo_client, demo_settings, staff_username):
    body = {"username": staff_username, "password": STAFF_PASSWORD}
    response = demo_client.post(LOGIN, json=body)
    assert response.status_code == 200
    out = response.json()
    assert (out["user_id"], out["role"]) == ("demo-officer", "officer")
    principal = decode_token(out["token"], demo_settings)
    assert (principal.user_id, principal.role) == ("demo-officer", Role.OFFICER)


def test_demo_login_token_opens_the_staff_routes(demo_client, staff_username):
    body = {"username": staff_username, "password": STAFF_PASSWORD}
    token = demo_client.post(LOGIN, json=body).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = demo_client.post("/v1/coach/ask", headers=headers, json={"question": "phí"})
    assert response.status_code == 403  # officers do not use the citizen coach


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("canbo-khac", STAFF_PASSWORD),
        (None, STAFF_PASSWORD + "x"),
        (None, STAFF_PASSWORD[:-1]),
        ("canbo-khac", "sai-mat-khau"),
    ],
    ids=["wrong-username", "longer-password", "shorter-password", "both-wrong"],
)
def test_demo_login_with_wrong_credentials_is_401(demo_client, staff_username, username, password):
    body = {"username": username or staff_username, "password": password}
    response = demo_client.post(LOGIN, json=body)
    assert response.status_code == 401
    error = response.json()["error"]
    assert error == {"code": "INVALID_CREDENTIALS", "message": INVALID_CREDENTIALS}


def test_login_is_501_when_demo_is_off(client, staff_username):
    response = client.post(LOGIN, json={"username": staff_username, "password": STAFF_PASSWORD})
    assert response.status_code == 501
    assert response.json()["error"]["details"] == {"epic": "E10"}


def test_demo_login_compares_username_and_password_in_constant_time(
    demo_client, monkeypatch, staff_username
):
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def _spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(auth_router.hmac, "compare_digest", _spy)
    demo_client.post(LOGIN, json={"username": "canbo-khac", "password": "sai-mat-khau"})
    assert len(calls) == 2  # both checks run even when the username is already wrong


def test_login_password_only_does_not_enable_join(settings_factory):
    only_login = settings_factory(ctcv_demo_staff_password=STAFF_PASSWORD)
    with TestClient(create_app(only_login)) as test_client:
        response = test_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"})
    assert response.status_code == 501


def test_demo_secrets_never_reach_the_logs(demo_client, caplog, staff_username):
    caplog.set_level(logging.DEBUG)
    demo_client.post(JOIN, json={"qr_token": QR_TOKEN, "display_name": "HV01"})
    demo_client.post(JOIN, json={"qr_token": QR_TOKEN + "x", "display_name": "HV01"})
    demo_client.post(LOGIN, json={"username": staff_username, "password": STAFF_PASSWORD})
    demo_client.post(LOGIN, json={"username": staff_username, "password": "sai-mat-khau-1"})
    assert QR_TOKEN not in caplog.text and STAFF_PASSWORD not in caplog.text
    assert "sai-mat-khau-1" not in caplog.text


# ---------------------------------------------------------------- settings
def test_demo_is_off_by_default():
    settings = Settings(_env_file=None)
    assert settings.ctcv_demo_qr_token is None
    assert settings.ctcv_demo_staff_password is None


def test_demo_secrets_are_read_from_the_environment(monkeypatch):
    # v2: demo mode now needs a JWT secret of its own (red-team F-08).
    monkeypatch.setenv("JWT_SECRET", REAL_JWT)
    monkeypatch.setenv("CTCV_DEMO_QR_TOKEN", QR_TOKEN)
    monkeypatch.setenv("CTCV_DEMO_STAFF_PASSWORD", STAFF_PASSWORD)
    settings = Settings(_env_file=None)
    assert settings.ctcv_demo_qr_token.get_secret_value() == QR_TOKEN
    assert settings.ctcv_demo_staff_password.get_secret_value() == STAFF_PASSWORD
    assert QR_TOKEN not in repr(settings) and STAFF_PASSWORD not in repr(settings)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_demo_variables_mean_demo_off(monkeypatch, blank):
    monkeypatch.setenv("CTCV_DEMO_QR_TOKEN", blank)
    monkeypatch.setenv("CTCV_DEMO_STAFF_PASSWORD", blank)
    settings = Settings(_env_file=None)
    assert settings.ctcv_demo_qr_token is None and settings.ctcv_demo_staff_password is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ctcv_demo_qr_token", "short-token-15c"),
        ("ctcv_demo_staff_password", "short-pw-11"),
    ],
)
def test_too_short_demo_secret_is_rejected_without_echo(field, value):
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None, jwt_secret=REAL_JWT, **{field: value})
    assert value not in str(info.value)
    assert any(ord(ch) > 127 for ch in str(info.value)), "message must be Vietnamese"


def test_minimum_lengths_are_accepted():
    settings = Settings(
        _env_file=None,
        jwt_secret=REAL_JWT,  # v2: demo mode needs its own JWT secret (red-team F-08)
        ctcv_demo_qr_token="t" * 16,
        ctcv_demo_staff_password="p" * 12,
    )
    assert settings.ctcv_demo_qr_token is not None


@pytest.mark.parametrize(
    "demo",
    [
        {"ctcv_demo_qr_token": QR_TOKEN},
        {"ctcv_demo_staff_password": STAFF_PASSWORD},
        {"ctcv_demo_qr_token": QR_TOKEN, "ctcv_demo_staff_password": STAFF_PASSWORD},
    ],
    ids=["qr-token", "staff-password", "both"],
)
def test_prod_refuses_to_start_with_demo_enabled(demo):
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None, ctcv_env="prod", jwt_secret=REAL_JWT, **demo)
    text = str(info.value)
    assert "prod" in text and "demo" in text.lower()
    assert QR_TOKEN not in text and STAFF_PASSWORD not in text and REAL_JWT not in text


def test_prod_refusal_also_applies_to_environment_variables(monkeypatch):
    monkeypatch.setenv("CTCV_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", REAL_JWT)
    monkeypatch.setenv("CTCV_DEMO_QR_TOKEN", QR_TOKEN)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_prod_without_demo_still_starts():
    settings = Settings(_env_file=None, ctcv_env="prod", jwt_secret=REAL_JWT)
    assert settings.ctcv_demo_qr_token is None


# ----------------------------------------------------------------------------- v2 (red-team)
@pytest.mark.parametrize("env", ["production", "PROD", " Prod ", "Production"])
def test_prod_spellings_are_all_prod_and_refuse_demo(env):
    # Red-team F-07 (IC-E01…E03): only the exact string "prod" used to count.
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None, ctcv_env=env, jwt_secret=REAL_JWT, ctcv_demo_qr_token=QR_TOKEN)
    assert "prod" in str(info.value) and QR_TOKEN not in str(info.value)
    assert Settings(_env_file=None, ctcv_env=env, jwt_secret=REAL_JWT).ctcv_env == "prod"


@pytest.mark.parametrize("secret", [None, "CHANGE_ME"])
def test_demo_mode_refuses_the_public_default_jwt_secret(secret):
    # Red-team F-08 (IC-E04): with the default secret anyone could forge an officer token.
    extra = {} if secret is None else {"jwt_secret": secret}
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None, ctcv_env="dev", ctcv_demo_staff_password=STAFF_PASSWORD, **extra)
    assert "JWT_SECRET" in str(info.value) and STAFF_PASSWORD not in str(info.value)


def test_non_prod_environment_names_are_normalised():
    assert Settings(_env_file=None, ctcv_env=" Dev ").ctcv_env == "dev"
