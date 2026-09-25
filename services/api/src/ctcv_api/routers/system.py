"""``/health`` and ``/metrics`` — mounted both under ``/v1`` and at the root."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from ctcv_api import get_version
from ctcv_api.health import overall_status, run_checks
from ctcv_api.metrics import render
from ctcv_api.schemas import HealthOut

router = APIRouter(tags=["system"])
DEGRADED_STATUS = 503


@router.get(
    "/health",
    response_model=HealthOut,
    responses={DEGRADED_STATUS: {"model": HealthOut, "description": "Một kiểm tra bị lỗi"}},
    summary="Kiểm tra sức khỏe dịch vụ",
)
async def health(request: Request, response: Response) -> HealthOut:
    """Run the db/redis/qdrant checks; 503 when any of them reports ``error``."""
    state = request.app.state
    checks = await run_checks(state.settings, state.engine)
    status = overall_status(checks)
    if status == "degraded":
        response.status_code = DEGRADED_STATUS
    return HealthOut(status=status, version=get_version(), checks=checks)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Chỉ số Prometheus",
)
def metrics(request: Request) -> Response:
    """Expose the application's Prometheus registry."""
    body, content_type = render(request.app.state.metrics)
    return Response(content=body, media_type=content_type)
