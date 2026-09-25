"""``/v1/coach`` — grounded TTHC Q&A, officer intake checklist (ADR-007) and screenshots (E08).

``/ask`` and ``/intake-check`` delegate to the services wired by :mod:`ctcv_api.knowledge`.
The citizen's question is passed on but never logged or stored here; an unexpected service
failure is logged by exception type only (its message could quote the question) and answered
with a generic 500. ``AppError`` subclasses (``KB_NOT_READY`` 503, ``PROCEDURE_NOT_FOUND``
404…) keep their own status.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from pydantic import ValidationError

from ctcv_agent.contracts import AskResult, IntakeRequest, IntakeResult
from ctcv_agent.schemas import SessionContext
from ctcv_api.auth import Citizen, CitizenOrVolunteer, Staff
from ctcv_api.errors import AnswerFailedError, IntakeFailedError, not_implemented
from ctcv_api.knowledge import AnswerServiceDep, IntakeServiceDep
from ctcv_api.schemas import (
    AskIn,
    AskOut,
    ErrorResponse,
    IntakeCheckIn,
    IntakeCheckOut,
    ScreenOut,
)
from ctcv_core.errors import AppError, ValidationFailed

log = logging.getLogger(__name__)
router = APIRouter(prefix="/coach", tags=["coach"])
SCREEN_EPIC = "E08"
AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    403: {"model": ErrorResponse, "description": "Sai vai"},
}
STUB_RESPONSES = {
    **AUTH_RESPONSES,
    501: {"model": ErrorResponse, "description": "Chưa hiện thực"},
}
KB_RESPONSES = {
    **AUTH_RESPONSES,
    500: {"model": ErrorResponse, "description": "Lỗi bất ngờ (không kèm chi tiết)"},
    503: {"model": ErrorResponse, "description": "KB_NOT_READY — kho thủ tục đang cập nhật"},
}
INTAKE_RESPONSES = {
    **KB_RESPONSES,
    404: {"model": ErrorResponse, "description": "PROCEDURE_NOT_FOUND — không có thủ tục này"},
}


def to_ask_out(result: AskResult) -> AskOut:
    """Map an engine result to the wire model, dropping ``diagnostics``."""
    return AskOut.model_validate(result.model_dump(mode="json", exclude={"diagnostics"}))


def to_intake_out(result: IntakeResult) -> IntakeCheckOut:
    """Map a checklist result to the wire model."""
    return IntakeCheckOut.model_validate(result.model_dump(mode="json"))


@router.post(
    "/ask",
    response_model=AskOut,
    responses=KB_RESPONSES,
    summary="Hỏi thủ tục hành chính có căn cứ (trích dẫn trang gốc) hoặc chuyển tình nguyện viên",
)
def ask(body: AskIn, user: Citizen, service: AnswerServiceDep) -> AskOut:
    """Answer a citizen question with citations, a safety line or a "not sure" escalation."""
    ctx = SessionContext(user_id=user.user_id, role="citizen")
    try:
        return to_ask_out(service.ask(body.question, ctx))
    except AppError:
        raise
    except Exception as exc:
        log.error("answer service failed", extra={"error_type": type(exc).__name__})
        raise AnswerFailedError() from None


def _intake_request(body: IntakeCheckIn) -> IntakeRequest:
    """Convert the wire request; any stricter engine rule becomes a 422, never a 500."""
    try:
        return IntakeRequest.model_validate(body.model_dump())
    except ValidationError:
        error = {"loc": ["body"], "msg": "không khớp hợp đồng kiểm hồ sơ", "type": "contract"}
        raise ValidationFailed(details={"errors": [error]}) from None


@router.post(
    "/intake-check",
    response_model=IntakeCheckOut,
    responses=INTAKE_RESPONSES,
    summary="Cán bộ kiểm hồ sơ: đánh dấu giấy tờ đã nhận, biết còn thiếu gì (không dùng LLM)",
)
def intake_check(body: IntakeCheckIn, user: Staff, service: IntakeServiceDep) -> IntakeCheckOut:
    """Build the received/missing checklist of a procedure for a volunteer or an officer."""
    request = _intake_request(body)
    try:
        return to_intake_out(service.check(request))
    except AppError:
        raise
    except Exception as exc:
        log.error("intake service failed", extra={"error_type": type(exc).__name__})
        raise IntakeFailedError() from None


@router.post(
    "/screen",
    response_model=ScreenOut,
    responses=STUB_RESPONSES,
    summary="Ảnh màn hình → bước tiếp theo (ảnh xóa sau 60 s)",
)
def screen(
    user: CitizenOrVolunteer,
    image: Annotated[UploadFile, File(description="Ảnh chụp màn hình (jpg/png)")],
) -> ScreenOut:
    """Detect the screen state and say the next step (E08)."""
    raise not_implemented(SCREEN_EPIC)
