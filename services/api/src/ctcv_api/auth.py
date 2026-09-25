"""JWT (HS256, short TTL) helpers and FastAPI dependencies for the three roles.

``create_token`` mints a token; ``current_user`` reads ``Authorization: Bearer``
and returns a :class:`Principal`; ``require_role`` builds a dependency that
rejects every other role with 403. The user id never comes from a request
parameter — only from the token (brief D28).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ctcv_api.enums import Role
from ctcv_api.errors import UnauthorizedError
from ctcv_api.settings import Settings
from ctcv_core.errors import Forbidden

ALGORITHM = "HS256"
REQUIRED_CLAIMS = ("exp", "iat", "sub", "role")

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT do /v1/auth/join hoặc /v1/auth/login cấp",
)


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller: id (from the token subject) and role."""

    user_id: str
    role: Role


def create_token(
    user_id: str,
    role: Role | str,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> str:
    """Mint an HS256 JWT for ``user_id``/``role`` valid for ``settings.jwt_ttl_minutes``."""
    issued = now or datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": Role(role).value,
        "iat": issued,
        "exp": issued + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_token(token: str, settings: Settings) -> Principal:
    """Verify ``token`` and return its principal; raise ``UnauthorizedError`` otherwise."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": list(REQUIRED_CLAIMS)},
        )
        role = Role(claims["role"])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            "Phiên học đã hết hạn, bác quét lại mã QR của lớp nhé.", code="TOKEN_EXPIRED"
        ) from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise UnauthorizedError(
            "Mã vào lớp không hợp lệ, bác quét lại mã QR của lớp nhé.", code="TOKEN_INVALID"
        ) from exc
    return Principal(user_id=str(claims["sub"]), role=role)


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """Dependency: the caller identified by the bearer token (401 when missing/invalid)."""
    if credentials is None or not credentials.credentials.strip():
        raise UnauthorizedError()
    settings: Settings = request.app.state.settings
    return decode_token(credentials.credentials.strip(), settings)


CurrentUser = Annotated[Principal, Depends(current_user)]


def require_role(*roles: Role | str) -> Callable[[Principal], Principal]:
    """Build a dependency that only lets the given roles through (403 otherwise)."""
    allowed = frozenset(Role(role) for role in roles)
    if not allowed:
        raise ValueError("require_role() needs at least one role")

    def _dependency(user: CurrentUser) -> Principal:
        if user.role not in allowed:
            raise Forbidden(details={"required": sorted(role.value for role in allowed)})
        return user

    return _dependency


Citizen = Annotated[Principal, Depends(require_role(Role.CITIZEN))]
Volunteer = Annotated[Principal, Depends(require_role(Role.VOLUNTEER))]
Staff = Annotated[Principal, Depends(require_role(Role.VOLUNTEER, Role.OFFICER))]
CitizenOrVolunteer = Annotated[Principal, Depends(require_role(Role.CITIZEN, Role.VOLUNTEER))]
