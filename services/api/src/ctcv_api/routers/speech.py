"""``/v1/speech`` — ASR (multipart audio) and TTS (E04)."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from ctcv_api.auth import CurrentUser
from ctcv_api.errors import not_implemented
from ctcv_api.schemas import AsrOut, ErrorResponse, TtsIn, TtsOut

router = APIRouter(prefix="/speech", tags=["speech"])
EPIC = "E04"
STUB_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai JWT"},
    501: {"model": ErrorResponse, "description": "Chưa hiện thực (E04)"},
}


@router.post(
    "/asr",
    response_model=AsrOut,
    responses=STUB_RESPONSES,
    summary="Âm thanh → văn bản (PhoWhisper)",
)
def asr(
    user: CurrentUser,
    audio: Annotated[UploadFile, File(description="File âm thanh (wav/webm/ogg)")],
) -> AsrOut:
    """Transcribe an uploaded audio clip (E04)."""
    raise not_implemented(EPIC)


@router.post(
    "/tts",
    response_model=TtsOut,
    responses=STUB_RESPONSES,
    summary="Văn bản → giọng nói (có bộ nhớ tạm)",
)
def tts(body: TtsIn, user: CurrentUser) -> TtsOut:
    """Synthesise speech for ``body.text`` and return a cached audio URL (E04)."""
    raise not_implemented(EPIC)
