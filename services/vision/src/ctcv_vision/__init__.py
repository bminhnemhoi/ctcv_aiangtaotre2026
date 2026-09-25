"""ctcv-vision: UI-element detection, screen reading and PII masking for the coach.

E01 ships the skeleton: ``/health`` works, ``POST /detect`` and ``POST /screen`` answer 501
``NOT_IMPLEMENTED`` until E08. The pure-Python helpers in :mod:`ctcv_vision.redact`
(``mask_regions``, ``redact_digits_in_text``) and :mod:`ctcv_vision.ttl` (``is_expired``)
are real and tested — they need no image library.
"""

from ctcv_vision.redact import MaskRegion, mask_regions, redact_digits_in_text
from ctcv_vision.settings import VisionSettings
from ctcv_vision.ttl import expires_at, is_expired, seconds_left

SERVICE_NAME = "vision"

__all__ = [
    "SERVICE_NAME",
    "MaskRegion",
    "VisionSettings",
    "expires_at",
    "is_expired",
    "mask_regions",
    "redact_digits_in_text",
    "seconds_left",
]
