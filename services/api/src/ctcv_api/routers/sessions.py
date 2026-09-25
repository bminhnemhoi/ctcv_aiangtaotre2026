"""``/v1/sessions`` — start a sandbox session and stream coach feedback over SSE.

``POST /v1/sessions/{session_id}/events`` is declared as an SSE endpoint from E01
on; until E02 it emits a single ``error`` event carrying the unified
``NOT_IMPLEMENTED`` body so clients can already wire up their EventSource parser.
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ctcv_api.auth import Citizen
from ctcv_api.errors import not_implemented
from ctcv_api.schemas import ErrorResponse, SessionCreate, SessionEvent, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])
EPIC = "E02"
SSE_MEDIA_TYPE = "text/event-stream"
STUB_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    403: {"model": ErrorResponse, "description": "Sai vai"},
    501: {"model": ErrorResponse, "description": "Chưa hiện thực (E02)"},
}


@router.post(
    "",
    response_model=SessionOut,
    responses=STUB_RESPONSES,
    summary="Bắt đầu phiên tập trên ứng dụng mô phỏng",
)
def create_session(body: SessionCreate, user: Citizen) -> SessionOut:
    """Start a session for the calling citizen and return the first screen (E02)."""
    raise not_implemented(EPIC)


async def _single_event(payload: dict[str, Any]) -> AsyncIterator[dict[str, str]]:
    """Yield exactly one SSE frame."""
    yield {"event": "error", "data": json.dumps(payload, ensure_ascii=False)}


@router.post(
    "/{session_id}/events",
    status_code=501,
    responses={
        **STUB_RESPONSES,
        501: {
            "description": "Luồng SSE; E01 phát đúng một sự kiện `error` NOT_IMPLEMENTED",
            "content": {SSE_MEDIA_TYPE: {"example": "event: error\ndata: {...}\n\n"}},
        },
    },
    summary="Gửi hành động, nhận trạng thái mới + câu huấn luyện viên (SSE)",
)
async def push_event(
    session_id: uuid.UUID, body: SessionEvent, user: Citizen
) -> EventSourceResponse:
    """Apply one learner action and stream ``{state, say}`` frames (E02)."""
    error = not_implemented(EPIC)
    return EventSourceResponse(_single_event(error.to_response()), status_code=error.status)
