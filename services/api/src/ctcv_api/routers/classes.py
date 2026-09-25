"""``/v1/classes`` — create a class (volunteer) and read its progress (volunteer/officer)."""

import uuid

from fastapi import APIRouter

from ctcv_api.auth import Staff, Volunteer
from ctcv_api.errors import not_implemented
from ctcv_api.schemas import ClassCreate, ClassOut, ClassProgress, ErrorResponse

router = APIRouter(prefix="/classes", tags=["classes"])
EPIC = "E10"
STUB_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    403: {"model": ErrorResponse, "description": "Sai vai"},
    501: {"model": ErrorResponse, "description": "Chưa hiện thực (E10)"},
}


@router.post(
    "",
    response_model=ClassOut,
    responses=STUB_RESPONSES,
    summary="Tạo lớp và sinh mã QR (tình nguyện viên)",
)
def create_class(body: ClassCreate, user: Volunteer) -> ClassOut:
    """Create a class owned by the calling volunteer and mint its QR token (E10)."""
    raise not_implemented(EPIC)


@router.get(
    "/{class_id}/progress",
    response_model=ClassProgress,
    responses=STUB_RESPONSES,
    summary="Tiến độ từng học viên và gợi ý kèm riêng",
)
def class_progress(class_id: uuid.UUID, user: Staff) -> ClassProgress:
    """Aggregate sessions/drills of a class into a progress table (E10)."""
    raise not_implemented(EPIC)
