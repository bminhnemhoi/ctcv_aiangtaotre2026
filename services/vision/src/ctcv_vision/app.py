"""FastAPI application of the vision service.

Routes (no ``/v1`` prefix — ``services/api`` proxies ``/v1/coach/screen``):

* ``GET /health`` — status, version, model ids, TTL, checks (``skipped`` until E08).
* ``POST /detect`` — multipart ``image`` → ``DetectOut``; **501** until E08.
* ``POST /screen`` — multipart ``image`` → ``ScreenOut``; **501** until E08.

Errors use the unified body ``{"error": {"code", "message"}}`` from ``ctcv_core.errors``.
"""

from __future__ import annotations

from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ctcv_core import AppError, NotImplementedYet, ValidationFailed, get_version
from ctcv_core.logging import setup_logging
from ctcv_vision.schemas import DetectOut, HealthOut, ScreenOut
from ctcv_vision.settings import VisionSettings

SERVICE_NAME = "vision"
PENDING_EPIC = "E08"
SKIPPED = "skipped"


def not_implemented_yet(feature_vi: str, epic: str = PENDING_EPIC) -> NotImplementedYet:
    """Build the 501 error for a feature that lands in a later epic (message in Vietnamese)."""
    return NotImplementedYet(
        f"{feature_vi} đang được hoàn thiện ({epic}), bác quay lại sau nhé.",
        details={"epic": epic},
    )


def install_error_handlers(app: FastAPI) -> None:
    """Map ``AppError`` and request validation failures to the unified error body."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_response())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(part) for part in err["loc"]) for err in exc.errors()})
        error = ValidationFailed(details={"fields": fields})
        return JSONResponse(status_code=error.status, content=error.to_response())


def create_app(settings: VisionSettings | None = None) -> FastAPI:
    """Create the FastAPI app; ``settings`` defaults to ``VisionSettings.load()``."""
    cfg = settings or VisionSettings.load()
    app = FastAPI(title="CTCV vision", version=get_version())
    app.state.settings = cfg
    install_error_handlers(app)

    @app.get("/health", response_model=HealthOut)
    async def health() -> HealthOut:
        return HealthOut(
            status="ok",
            service=SERVICE_NAME,
            version=get_version(),
            checks={"ui_detector": SKIPPED, "vlm": SKIPPED, "screen_store": SKIPPED},
            models={"ui_detector": cfg.detector_model, "vlm": cfg.vlm_model},
            screen_ttl_seconds=cfg.screen_ttl_seconds,
        )

    @app.post("/detect", response_model=DetectOut, status_code=200)
    async def detect(image: Annotated[UploadFile, File()]) -> DetectOut:
        del image  # parsed only to validate the multipart contract; YOLOX inference lands in E08
        raise not_implemented_yet("Phần nhận diện nút trên ảnh")

    @app.post("/screen", response_model=ScreenOut, status_code=200)
    async def screen(image: Annotated[UploadFile, File()]) -> ScreenOut:
        del image  # validated for the contract; VLM reading, masking and TTL store land in E08
        raise not_implemented_yet("Phần đọc màn hình qua ảnh")

    return app


def main() -> None:
    """Serve the app with uvicorn on ``config/app.yaml: ports.vision``."""
    settings = VisionSettings.load()
    setup_logging(SERVICE_NAME)
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)  # noqa: S104


if __name__ == "__main__":
    main()
