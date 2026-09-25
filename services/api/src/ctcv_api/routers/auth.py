"""``/v1/auth`` — join a class by QR (citizen) and password login (volunteer/officer).

Real classes and accounts land in E10; until then both endpoints answer 501. ADR-007 adds a
demo mode for the DA940-01 prototype, off unless the environment sets it (C6, C10):

* ``CTCV_DEMO_QR_TOKEN`` — ``join`` with this exact token returns a citizen JWT whose id is
  ``demo-citizen-<sha256(display_name)[:8]>`` (the nickname itself is not kept);
* ``CTCV_DEMO_STAFF_PASSWORD`` — ``login`` as ``config/rag.yaml: demo.staff_username`` with
  this password returns an officer JWT for ``demo-officer``; a wrong pair is 401.

Secrets are compared with :func:`hmac.compare_digest` on UTF-8 bytes and never logged. The
settings refuse to start in ``prod`` when a demo secret is set.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Request
from pydantic import SecretStr

from ctcv_agent.rag.settings import load_rag_settings
from ctcv_api.auth import create_token
from ctcv_api.enums import Role
from ctcv_api.errors import InvalidCredentialsError, not_implemented
from ctcv_api.schemas import ErrorResponse, JoinRequest, LoginRequest, TokenResponse
from ctcv_api.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])
EPIC = "E10"
DEMO_CITIZEN_PREFIX = "demo-citizen-"
DEMO_CITIZEN_HASH_CHARS = 8
DEMO_OFFICER_ID = "demo-officer"
STUB_RESPONSES = {501: {"model": ErrorResponse, "description": "Chưa hiện thực (E10)"}}
LOGIN_RESPONSES = {
    **STUB_RESPONSES,
    401: {"model": ErrorResponse, "description": "INVALID_CREDENTIALS (chế độ demo)"},
}


def _same_secret(given: str, expected: SecretStr) -> bool:
    """Constant-time comparison of a submitted value with a configured secret."""
    return hmac.compare_digest(given.encode("utf-8"), expected.get_secret_value().encode("utf-8"))


def demo_citizen_id(display_name: str) -> str:
    """Pseudonymous demo id derived from the nickname (the nickname is not stored)."""
    digest = hashlib.sha256(display_name.encode("utf-8")).hexdigest()
    return DEMO_CITIZEN_PREFIX + digest[:DEMO_CITIZEN_HASH_CHARS]


@router.post(
    "/join",
    response_model=TokenResponse,
    responses=STUB_RESPONSES,
    summary="Người dân vào lớp bằng mã QR và biệt danh",
)
def join(body: JoinRequest, request: Request) -> TokenResponse:
    """Exchange the demo QR token plus a nickname for a citizen JWT; otherwise 501 (E10)."""
    settings: Settings = request.app.state.settings
    expected = settings.ctcv_demo_qr_token
    if expected is None or not _same_secret(body.qr_token, expected):
        raise not_implemented(EPIC)
    user_id = demo_citizen_id(body.display_name)
    token = create_token(user_id, Role.CITIZEN, settings)
    return TokenResponse(token=token, user_id=user_id, role=Role.CITIZEN)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses=LOGIN_RESPONSES,
    summary="Tình nguyện viên / cán bộ đăng nhập",
)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Demo officer login when configured (401 on a wrong pair); otherwise 501 (E10)."""
    settings: Settings = request.app.state.settings
    password = settings.ctcv_demo_staff_password
    if password is None:
        raise not_implemented(EPIC)
    username = SecretStr(load_rag_settings().demo_staff_username)
    username_ok = _same_secret(body.username, username)
    password_ok = _same_secret(body.password, password)  # always evaluated: no early exit
    if not (username_ok and password_ok):
        raise InvalidCredentialsError()
    token = create_token(DEMO_OFFICER_ID, Role.OFFICER, settings)
    return TokenResponse(token=token, user_id=DEMO_OFFICER_ID, role=Role.OFFICER)
