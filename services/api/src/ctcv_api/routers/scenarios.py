"""``/v1/scenarios`` — list sandbox scenarios (real in E01)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from ctcv_api.auth import CurrentUser
from ctcv_api.scenarios_source import list_scenario_summaries
from ctcv_api.schemas import ErrorResponse, ScenarioSummary
from ctcv_core.config import load_config
from ctcv_core.errors import ValidationFailed

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
LEVEL_MIN, LEVEL_MAX = 1, 3


def allowed_skill_groups() -> list[str]:
    """Skill groups declared in ``config/app.yaml``."""
    return list(load_config("app")["skill_groups"])


@router.get(
    "",
    response_model=list[ScenarioSummary],
    responses={
        401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
        422: {"model": ErrorResponse, "description": "Nhóm kỹ năng hoặc mức không hợp lệ"},
    },
    summary="Danh sách kịch bản theo kỹ năng và mức",
)
def list_scenarios(
    request: Request,
    user: CurrentUser,
    skill: Annotated[str | None, Query(description="Nhóm kỹ năng (skill_group)")] = None,
    level: Annotated[
        int | None, Query(ge=LEVEL_MIN, le=LEVEL_MAX, description="Mức độ 1..3")
    ] = None,
) -> list[ScenarioSummary]:
    """Return scenario summaries, optionally filtered by ``skill`` and ``level``."""
    groups = allowed_skill_groups()
    if skill is not None and skill not in groups:
        raise ValidationFailed(
            "Nhóm kỹ năng này không có, bác chọn lại giúp cháu nhé.",
            code="SKILL_INVALID",
            details={"allowed": groups},
        )
    return list_scenario_summaries(
        skill=skill, level=level, directory=request.app.state.settings.scenarios_dir
    )
