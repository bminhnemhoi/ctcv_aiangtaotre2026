"""``/v1/drills`` — scam-vaccine drills (E09).

There is deliberately **no** endpoint that lists drills (brief D27): the server
picks the variant when a drill starts, so the catalogue cannot be scraped.
"""

import uuid

from fastapi import APIRouter

from ctcv_api.auth import Citizen
from ctcv_api.errors import not_implemented
from ctcv_api.schemas import DrillAnswer, DrillOut, DrillResult, DrillStart, ErrorResponse

router = APIRouter(prefix="/drills", tags=["drills"])
EPIC = "E09"
STUB_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    403: {"model": ErrorResponse, "description": "Sai vai"},
    501: {"model": ErrorResponse, "description": "Chưa hiện thực (E09)"},
}


@router.post(
    "",
    response_model=DrillOut,
    responses=STUB_RESPONSES,
    summary="Bắt đầu một lượt vắc-xin lừa đảo (server chọn biến thể)",
)
def start_drill(body: DrillStart, user: Citizen) -> DrillOut:
    """Start a drill for the calling citizen (E09)."""
    raise not_implemented(EPIC)


@router.post(
    "/{drill_id}/answers",
    response_model=DrillResult,
    responses=STUB_RESPONSES,
    summary="Chọn cách xử lý, nhận điểm và giải thích",
)
def answer_drill(drill_id: uuid.UUID, body: DrillAnswer, user: Citizen) -> DrillResult:
    """Grade the chosen option and return the debrief (E09)."""
    raise not_implemented(EPIC)
