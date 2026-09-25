"""JWT minting/decoding and the role dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from ctcv_api.auth import ALGORITHM, Principal, create_token, decode_token, require_role
from ctcv_api.enums import Role
from ctcv_api.errors import UnauthorizedError
from ctcv_core.config import load_config


def test_roles_match_config():
    assert [role.value for role in Role] == load_config("app")["roles"]


def test_token_roundtrip(settings):
    token = create_token("u-1", "volunteer", settings)
    principal = decode_token(token, settings)
    assert principal == Principal(user_id="u-1", role=Role.VOLUNTEER)


def test_token_is_short_lived(settings):
    issued = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)
    token = create_token("u-1", Role.CITIZEN, settings, now=issued)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == settings.jwt_ttl_minutes * 60
    assert claims["sub"] == "u-1" and claims["role"] == "citizen"


def test_expired_token_is_401_token_expired(settings):
    past = datetime.now(UTC) - timedelta(minutes=settings.jwt_ttl_minutes + 1)
    token = create_token("u-1", Role.CITIZEN, settings, now=past)
    with pytest.raises(UnauthorizedError) as info:
        decode_token(token, settings)
    assert info.value.code == "TOKEN_EXPIRED" and info.value.status == 401


def test_tampered_token_is_401_token_invalid(settings):
    token = create_token("u-1", Role.CITIZEN, settings)
    with pytest.raises(UnauthorizedError) as info:
        decode_token(token[:-3] + "abc", settings)
    assert info.value.code == "TOKEN_INVALID"


def test_token_signed_with_other_secret_is_rejected(settings, settings_factory):
    other = settings_factory(jwt_secret="another-secret-of-at-least-32-bytes")
    token = create_token("u-1", Role.CITIZEN, other)
    with pytest.raises(UnauthorizedError):
        decode_token(token, settings)


def test_token_with_unknown_role_is_rejected(settings):
    now = datetime.now(UTC)
    claims = {"sub": "u-1", "role": "admin", "iat": now, "exp": now + timedelta(minutes=5)}
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    with pytest.raises(UnauthorizedError) as info:
        decode_token(token, settings)
    assert info.value.code == "TOKEN_INVALID"


def test_token_missing_required_claims_is_rejected(settings):
    token = jwt.encode({"sub": "u-1"}, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    with pytest.raises(UnauthorizedError):
        decode_token(token, settings)


def test_unsigned_token_is_rejected(settings):
    now = datetime.now(UTC)
    claims = {"sub": "u-1", "role": "officer", "iat": now, "exp": now + timedelta(minutes=5)}
    token = jwt.encode(claims, "", algorithm="none")
    with pytest.raises(UnauthorizedError):
        decode_token(token, settings)


def test_create_token_rejects_unknown_role(settings):
    with pytest.raises(ValueError):
        create_token("u-1", "root", settings)


def test_require_role_needs_at_least_one_role():
    with pytest.raises(ValueError):
        require_role()


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer  ", "Token xyz", ""])
def test_malformed_authorization_header_is_401(client: TestClient, header):
    response = client.get("/v1/scenarios", headers={"Authorization": header})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_expired_token_over_http(client: TestClient, settings):
    past = datetime.now(UTC) - timedelta(hours=3)
    token = create_token("u-1", Role.CITIZEN, settings, now=past)
    response = client.get("/v1/scenarios", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"
