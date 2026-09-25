"""FastAPI application of the speech service.

Routes (no ``/v1`` prefix — the public API in ``services/api`` proxies ``/v1/speech/*``):

* ``GET /health`` — status, version, model ids, checks (``skipped`` until E04 loads models).
* ``POST /asr`` — multipart ``audio`` → ``AsrOut``; **501** until E04.
* ``POST /tts`` — JSON ``TtsIn`` → ``TtsOut``; **501** until E04.

Every error — ``AppError``, request validation and the framework's own 404/405 — uses the
unified body ``{"error": {"code", "message"}}`` from ``ctcv_core.errors`` (brief §3).
"""

from __future__ import annotations

from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ctcv_core import AppError, NotFound, NotImplementedYet, ValidationFailed, get_version
from ctcv_core.logging import setup_logging
from ctcv_speech.schemas import AsrOut, HealthOut, TtsIn, TtsOut
from ctcv_speech.settings import SpeechSettings

SERVICE_NAME = "speech"
PENDING_EPIC = "E04"
SKIPPED = "skipped"
# Vietnamese messages for statuses the framework raises itself (route or method mismatch).
HTTP_ERRORS_VI: dict[int, tuple[str, str]] = {
    405: ("METHOD_NOT_ALLOWED", "Cách gọi này chưa được hỗ trợ, bác thử lại giúp cháu nhé."),
}
GENERIC_HTTP_MESSAGE_VI = "Có lỗi xảy ra, bác thử lại sau nhé."


def not_implemented_yet(feature_vi: str, epic: str = PENDING_EPIC) -> NotImplementedYet:
    """Build the 501 error for a feature that lands in a later epic (message in Vietnamese)."""
    return NotImplementedYet(
        f"{feature_vi} đang được hoàn thiện ({epic}), bác quay lại sau nhé.",
        details={"epic": epic},
    )


def http_error(status: int) -> AppError:
    """Translate a framework-raised HTTP status into an ``AppError`` with a Vietnamese message."""
    if status == NotFound.STATUS:
        return NotFound()
    code, message = HTTP_ERRORS_VI.get(status, (f"HTTP_{status}", GENERIC_HTTP_MESSAGE_VI))
    return AppError(code, message, status=status)


def check_text_length(text: str, max_chars: int) -> None:
    """Reject ``text`` longer than ``max_chars`` with a Vietnamese 422 naming ``body.text``."""
    if len(text) > max_chars:
        raise ValidationFailed(
            f"Văn bản dài quá {max_chars} ký tự, bác chia thành đoạn ngắn hơn giúp cháu nhé.",
            details={"fields": ["body.text"], "max_chars": max_chars, "chars": len(text)},
        )


def validation_message(errors: list[dict[str, Any]]) -> str | None:
    """Return the Vietnamese message of the first custom validator error, if any."""
    for err in errors:
        cause = (err.get("ctx") or {}).get("error")
        if isinstance(cause, ValueError) and str(cause):
            return str(cause)
    return None


def install_error_handlers(app: FastAPI) -> None:
    """Map ``AppError``, validation failures and framework HTTP errors to the unified body."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_response())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        fields = sorted({".".join(str(part) for part in err["loc"]) for err in errors})
        error = ValidationFailed(validation_message(errors), details={"fields": fields})
        return JSONResponse(status_code=error.status, content=error.to_response())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        error = http_error(exc.status_code)
        return JSONResponse(
            status_code=error.status, content=error.to_response(), headers=exc.headers
        )


def create_app(settings: SpeechSettings | None = None) -> FastAPI:
    """Create the FastAPI app; ``settings`` defaults to ``SpeechSettings.load()``."""
    cfg = settings or SpeechSettings.load()
    app = FastAPI(title="CTCV speech", version=get_version())
    app.state.settings = cfg
    install_error_handlers(app)

    @app.get("/health", response_model=HealthOut)
    async def health() -> HealthOut:
        """Report service status, version, configured model ids and per-dependency checks."""
        return HealthOut(
            status="ok",
            service=SERVICE_NAME,
            version=get_version(),
            checks={"asr_model": SKIPPED, "tts_model": SKIPPED, "tts_cache": SKIPPED},
            models={"asr": cfg.asr_model, "asr_small": cfg.asr_small_model, "tts": cfg.tts_model},
        )

    @app.post("/asr", response_model=AsrOut, status_code=200)
    async def asr(audio: Annotated[UploadFile, File()]) -> AsrOut:
        """Transcribe an uploaded clip (E04); today it validates the multipart contract only."""
        del audio  # parsed only to validate the multipart contract; transcription lands in E04
        raise not_implemented_yet("Phần nghe giọng nói")

    @app.post("/tts", response_model=TtsOut, status_code=200)
    async def tts(body: TtsIn) -> TtsOut:
        """Synthesise ``body.text`` (E04); today it validates the contract and length only."""
        check_text_length(body.text, cfg.tts_max_text_chars)
        raise not_implemented_yet("Phần đọc chữ thành tiếng")

    return app


def main() -> None:
    """Serve the app with uvicorn on ``config/app.yaml: ports.speech``."""
    settings = SpeechSettings.load()
    setup_logging(SERVICE_NAME)
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)  # noqa: S104


if __name__ == "__main__":
    main()
