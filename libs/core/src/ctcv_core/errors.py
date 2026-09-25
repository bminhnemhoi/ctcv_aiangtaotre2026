"""Application errors with a stable machine code and a Vietnamese user-facing message.

Every service converts these into the unified HTTP error body defined in the E01
brief (§3): ``{"error": {"code": "...", "message": "..."}}``.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base error carrying ``code``, ``message_vi``, HTTP ``status`` and optional details.

    Args:
        code: Stable upper-snake-case identifier (e.g. ``SCENARIO_NOT_FOUND``).
        message_vi: Plain-language Vietnamese message safe to show to citizens.
        status: HTTP status code to respond with.
        details: Optional structured context (never PII).
    """

    def __init__(
        self,
        code: str,
        message_vi: str,
        status: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Store the code, message, status and details; ``str(err)`` is ``"CODE: message"``."""
        super().__init__(f"{code}: {message_vi}")
        self.code = code
        self.message_vi = message_vi
        self.status = status
        self.details = details

    def to_response(self) -> dict[str, Any]:
        """Serialise to the unified error body ``{"error": {"code", "message"[, "details"]}}``."""
        body: dict[str, Any] = {"code": self.code, "message": self.message_vi}
        if self.details:
            body["details"] = self.details
        return {"error": body}

    def __repr__(self) -> str:
        """Return a debugging representation."""
        name = type(self).__name__
        return f"{name}(code={self.code!r}, status={self.status}, message_vi={self.message_vi!r})"


class _FixedStatusError(AppError):
    """Helper base for subclasses with a fixed status and default code/message."""

    DEFAULT_CODE = "APP_ERROR"
    DEFAULT_MESSAGE = "Có lỗi xảy ra, bác thử lại sau nhé."
    STATUS = 400

    def __init__(
        self,
        message_vi: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Use the class defaults unless a message/code is given."""
        super().__init__(
            code or self.DEFAULT_CODE,
            message_vi or self.DEFAULT_MESSAGE,
            self.STATUS,
            details,
        )


class NotImplementedYet(_FixedStatusError):
    """501 — endpoint or feature is stubbed and lands in a later epic."""

    DEFAULT_CODE = "NOT_IMPLEMENTED"
    DEFAULT_MESSAGE = "Phần này đang được hoàn thiện, bác quay lại sau nhé."
    STATUS = 501


class NotFound(_FixedStatusError):
    """404 — the requested resource does not exist."""

    DEFAULT_CODE = "NOT_FOUND"
    DEFAULT_MESSAGE = "Không tìm thấy nội dung này, bác thử chọn mục khác nhé."
    STATUS = 404


class Forbidden(_FixedStatusError):
    """403 — caller is authenticated but not allowed."""

    DEFAULT_CODE = "FORBIDDEN"
    DEFAULT_MESSAGE = "Bác chưa có quyền dùng phần này, nhờ tình nguyện viên giúp nhé."
    STATUS = 403


class ValidationFailed(_FixedStatusError):
    """422 — request body or config failed validation."""

    DEFAULT_CODE = "VALIDATION_FAILED"
    DEFAULT_MESSAGE = "Thông tin gửi lên chưa đúng, bác kiểm tra lại giúp cháu nhé."
    STATUS = 422
