"""Exception handlers mapping every failure onto the unified error body (brief §3).

``{"error": {"code": "...", "message": "<tiếng Việt>"[, "details": {...}]}}``
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ctcv_core.errors import AppError, ValidationFailed

log = logging.getLogger(__name__)

HTTP_ERROR_CODES: dict[int, tuple[str, str]] = {
    404: ("NOT_FOUND", "Không tìm thấy đường dẫn này, bác kiểm tra lại giúp cháu nhé."),
    405: ("METHOD_NOT_ALLOWED", "Cách gọi này chưa đúng, bác thử lại giúp cháu nhé."),
    401: ("UNAUTHORIZED", "Bác cần vào lớp bằng mã QR trước nhé."),
    403: ("FORBIDDEN", "Bác chưa có quyền dùng phần này, nhờ tình nguyện viên giúp nhé."),
    413: ("PAYLOAD_TOO_LARGE", "Tệp gửi lên quá lớn, bác chọn tệp nhỏ hơn nhé."),
    429: ("RATE_LIMITED", "Bác thao tác hơi nhanh, chờ một chút rồi thử lại nhé."),
}
GENERIC_HTTP_ERROR = ("HTTP_ERROR", "Có lỗi xảy ra, bác thử lại sau nhé.")
INTERNAL_ERROR = ("INTERNAL_ERROR", "Hệ thống gặp trục trặc, bác thử lại sau ít phút nhé.")


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    """Build the unified error JSON response."""
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def sanitize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only location/message/type — never echo the submitted input (may hold PII)."""
    return [
        {
            "loc": [str(part) for part in err.get("loc", ())],
            "msg": err.get("msg"),
            "type": err.get("type"),
        }
        for err in errors
    ]


async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    """``AppError`` → its own status and ``to_response()`` body."""
    return JSONResponse(status_code=exc.status, content=exc.to_response())


async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI request validation → 422 ``VALIDATION_FAILED``."""
    failed = ValidationFailed()
    return error_response(
        failed.status,
        failed.code,
        failed.message_vi,
        {"errors": sanitize_validation_errors(exc.errors())},
    )


async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Starlette/FastAPI ``HTTPException`` (404 route, 405 method...) → unified body."""
    code, message = HTTP_ERROR_CODES.get(exc.status_code, GENERIC_HTTP_ERROR)
    return error_response(exc.status_code, code, message)


async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
    """Anything else → 500 ``INTERNAL_ERROR`` (logged with traceback, no details leaked)."""
    log.exception("unhandled error", extra={"error_type": type(exc).__name__})
    return error_response(500, *INTERNAL_ERROR)


def install_exception_handlers(app: FastAPI) -> None:
    """Register the four handlers on ``app``."""
    app.add_exception_handler(AppError, handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected)
