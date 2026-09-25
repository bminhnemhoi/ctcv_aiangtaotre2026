"""ctcv-speech: ASR (PhoWhisper) and cached TTS for the coach.

E01 ships the service skeleton only: ``/health`` works, ``POST /asr`` and ``POST /tts``
answer 501 ``NOT_IMPLEMENTED`` until E04. Settings come from ``config/models.yaml``
(``asr``, ``asr_small``, ``tts``) and ``config/app.yaml`` (``ports.speech``), overridable with
``ASR_MODEL``, ``TTS_MODEL``, ``TTS_CACHE_DIR`` and ``SPEECH_PORT``.
"""

from ctcv_speech.cache import cache_key, cache_path, normalise_text
from ctcv_speech.settings import SpeechSettings

SERVICE_NAME = "speech"

__all__ = ["SERVICE_NAME", "SpeechSettings", "cache_key", "cache_path", "normalise_text"]
