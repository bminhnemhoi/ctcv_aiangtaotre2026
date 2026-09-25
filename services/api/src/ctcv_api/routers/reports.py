"""``/v1/reports`` — class report as PDF or XLSX (volunteer/officer)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ctcv_api.auth import Staff
from ctcv_api.errors import not_implemented
from ctcv_api.schemas import ErrorResponse, ReportFormat

router = APIRouter(prefix="/reports", tags=["reports"])
EPIC = "E10"
STUB_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    403: {"model": ErrorResponse, "description": "Sai vai"},
    501: {"model": ErrorResponse, "description": "Chưa hiện thực (E10)"},
}


@router.get(
    "/class/{class_id}",
    response_class=Response,
    responses=STUB_RESPONSES,
    summary="Xuất báo cáo lớp (PDF hoặc Excel)",
)
def class_report(
    class_id: uuid.UUID,
    user: Staff,
    format: Annotated[ReportFormat, Query(description="Định dạng file: pdf | xlsx")],
) -> Response:
    """Render the class report file in the requested format (E10)."""
    raise not_implemented(EPIC)
