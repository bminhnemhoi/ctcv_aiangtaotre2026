"""API-specific errors on top of :mod:`ctcv_core.errors` and the 501 stub helper.

KB errors (``KB_NOT_READY`` 503, ``PROCEDURE_NOT_FOUND`` 404) come from
``ctcv_agent.rag.types`` and reach the client through the generic ``AppError`` handler.
"""

from __future__ import annotations

from typing import Any

from ctcv_core.errors import AppError, NotImplementedYet

# Feature label (Vietnamese) per epic, used in the 501 message of stubbed endpoints.
EPIC_FEATURES: dict[str, str] = {
    "E02": "phiên tập trên ứng dụng mô phỏng",
    "E03": "hỏi đáp có căn cứ",
    "E04": "nói và nghe",
    "E08": "kèm cặp qua ảnh màn hình",
    "E09": "vắc-xin lừa đảo",
    "E10": "lớp học, đăng nhập và báo cáo",
}


class UnauthorizedError(AppError):
    """401 — no usable JWT was presented."""

    def __init__(
        self,
        message_vi: str | None = None,
        *,
        code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Create a 401 with a Vietnamese message safe to show to citizens."""
        super().__init__(
            code,
            message_vi or "Bác cần vào lớp bằng mã QR trước nhé.",
            401,
            details,
        )


class InvalidCredentialsError(AppError):
    """401 — demo staff login with a wrong username or password (ADR-007 C6)."""

    def __init__(self) -> None:
        """Create the 401 with the fixed Vietnamese message (never says which part is wrong)."""
        super().__init__(
            "INVALID_CREDENTIALS",
            "Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé.",
            401,
        )


class AnswerFailedError(AppError):
    """500 — the answer service failed unexpectedly; no detail is exposed or logged."""

    def __init__(self) -> None:
        """Create the 500 with a Vietnamese message that points to a volunteer."""
        super().__init__(
            "ANSWER_FAILED",
            "Cháu đang trục trặc khi tra thủ tục, bác thử lại sau ít phút "
            "hoặc hỏi tình nguyện viên giúp cháu nhé.",
            500,
        )


class IntakeFailedError(AppError):
    """500 — the officer checklist failed unexpectedly; no detail is exposed or logged."""

    def __init__(self) -> None:
        """Create the 500 with a Vietnamese message for the officer."""
        super().__init__(
            "INTAKE_FAILED",
            "Chưa lập được danh mục giấy tờ, anh/chị thử lại sau ít phút nhé.",
            500,
        )


def not_implemented(epic: str) -> NotImplementedYet:
    """Build the 501 error that names the epic delivering the feature."""
    feature = EPIC_FEATURES.get(epic, "phần này")
    return NotImplementedYet(
        f"Phần {feature} sẽ có ở epic {epic}, bác quay lại sau nhé.",
        details={"epic": epic},
    )
