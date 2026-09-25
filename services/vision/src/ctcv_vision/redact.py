"""PII masking helpers that need no image library (pure Python).

``mask_regions`` turns detector/VLM boxes into clamped, padded, merged pixel rectangles that
must be blurred **before** anything is stored (ADR-005, E08 SEC-05); ``apply_mask`` paints
them onto a 2-D pixel grid; ``redact_digits_in_text`` removes PII and every long digit run
from text read off a screen. Boxes follow the ``boxes_json`` contract ``[{cls,x,y,w,h}]`` —
no free text ever travels with a box.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ctcv_core.config import load_config
from ctcv_core.logging import DEFAULT_REDACTION, scrub_pii

# E08 / SEC-05: any digit run of this length or longer is masked after the PII regexes ran.
# Interim constant — E08 moves it into config/guardrails.yaml next to `pii_patterns`.
DEFAULT_MIN_DIGIT_RUN = 4
DEFAULT_CLASS = "pii"
MERGED_CLASS = "mixed"

BoxLike = Mapping[str, object] | Sequence[object]


@dataclass(frozen=True, slots=True)
class MaskRegion:
    """Axis-aligned pixel rectangle to blur; integer, inclusive-exclusive (``x + w``)."""

    cls: str
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        """Exclusive right edge."""
        return self.x + self.w

    @property
    def bottom(self) -> int:
        """Exclusive bottom edge."""
        return self.y + self.h

    def overlaps(self, other: MaskRegion) -> bool:
        """True when the two rectangles share at least one pixel."""
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )

    def union(self, other: MaskRegion) -> MaskRegion:
        """Smallest rectangle covering both; class kept when equal, ``mixed`` otherwise."""
        x0, y0 = min(self.x, other.x), min(self.y, other.y)
        x1, y1 = max(self.right, other.right), max(self.bottom, other.bottom)
        cls = self.cls if self.cls == other.cls else MERGED_CLASS
        return MaskRegion(cls, x0, y0, x1 - x0, y1 - y0)

    def to_dict(self) -> dict[str, int | str]:
        """Serialise to the ``boxes_json`` shape ``{cls, x, y, w, h}``."""
        return {"cls": self.cls, "x": self.x, "y": self.y, "w": self.w, "h": self.h}


def _coerce_box(box: BoxLike) -> tuple[str, float, float, float, float]:
    """Accept ``{cls?,x,y,w,h}``, ``{cls?, bbox:[x,y,w,h]}``, ``(x,y,w,h)`` or ``(cls,x,y,w,h)``."""
    if isinstance(box, Mapping):
        cls = str(box.get("cls", DEFAULT_CLASS))
        try:
            coords = box["bbox"] if "bbox" in box else (box["x"], box["y"], box["w"], box["h"])
        except KeyError as exc:
            raise ValueError(f"Khung thiếu tọa độ {exc.args[0]!r}: {box!r}") from exc
        if not isinstance(coords, Sequence) or len(coords) != 4:
            raise ValueError(f"Khung phải có 4 tọa độ x, y, w, h: {box!r}")
        return cls, *(float(c) for c in coords)  # type: ignore[arg-type]
    items = list(box)
    if len(items) == 5:
        return str(items[0]), *(float(c) for c in items[1:])  # type: ignore[arg-type]
    if len(items) == 4:
        return DEFAULT_CLASS, *(float(c) for c in items)  # type: ignore[arg-type]
    raise ValueError(f"Khung phải là (x, y, w, h) hoặc (cls, x, y, w, h): {box!r}")


def _looks_normalised(coords: tuple[float, float, float, float]) -> bool:
    return all(0.0 <= c <= 1.0 for c in coords)


def _merge_overlapping(regions: list[MaskRegion]) -> list[MaskRegion]:
    merged: list[MaskRegion] = []
    for region in regions:
        current = region
        remaining: list[MaskRegion] = []
        for existing in merged:
            if existing.overlaps(current):
                current = existing.union(current)
            else:
                remaining.append(existing)
        merged = [*remaining, current]
    return sorted(merged, key=lambda r: (r.y, r.x))


def mask_regions(
    boxes: Iterable[BoxLike],
    image_size: tuple[int, int],
    *,
    padding_px: int = 0,
    normalised: bool | None = None,
) -> list[MaskRegion]:
    """Convert ``boxes`` into pixel rectangles to blur on an image of ``image_size`` (w, h).

    Coordinates in ``[0, 1]`` are treated as normalised (the VLM ``bbox`` convention) unless
    ``normalised`` says otherwise. Degenerate boxes (zero width or height) are dropped; every
    other box is expanded by ``padding_px``, clamped to the image, dropped when nothing of it
    lies inside, and merged with any box it overlaps, so the caller cannot leak a sliver of
    a number between two adjacent regions.

    Raises:
        ValueError: on a non-positive image size, negative padding or a malformed box.
    """
    width, height = image_size
    if width <= 0 or height <= 0:
        raise ValueError(f"Kích thước ảnh phải dương, nhận được: {image_size!r}")
    if padding_px < 0:
        raise ValueError(f"padding_px phải ≥ 0, nhận được: {padding_px}")
    regions: list[MaskRegion] = []
    for box in boxes:
        cls, x, y, w, h = _coerce_box(box)
        if w <= 0 or h <= 0:
            continue
        if normalised or (normalised is None and _looks_normalised((x, y, w, h))):
            x, w = x * width, w * width
            y, h = y * height, h * height
        x0 = max(0, math.floor(x - padding_px))
        y0 = max(0, math.floor(y - padding_px))
        x1 = min(width, math.ceil(x + w + padding_px))
        y1 = min(height, math.ceil(y + h + padding_px))
        if x1 <= x0 or y1 <= y0:
            continue
        regions.append(MaskRegion(cls, x0, y0, x1 - x0, y1 - y0))
    return _merge_overlapping(regions)


def apply_mask[Pixel](
    pixels: Sequence[Sequence[Pixel]], regions: Iterable[MaskRegion], fill: Pixel
) -> list[list[Pixel]]:
    """Return a copy of the row-major ``pixels`` grid with every region painted ``fill``."""
    rows = [list(row) for row in pixels]
    for region in regions:
        for y in range(region.y, min(region.bottom, len(rows))):
            row = rows[y]
            for x in range(region.x, min(region.right, len(row))):
                row[x] = fill
    return rows


def redact_digits_in_text(
    text: str, *, min_digits: int = DEFAULT_MIN_DIGIT_RUN, token: str | None = None
) -> str:
    """Scrub PII with the ``config/guardrails.yaml`` patterns, then mask long digit runs.

    ``min_digits`` is the shortest digit run (spaces, dots and dashes between groups count
    as part of the run) that gets replaced; ``token`` defaults to ``redaction_token``.
    """
    if min_digits < 1:
        raise ValueError(f"min_digits phải ≥ 1, nhận được: {min_digits}")
    redaction = token if token is not None else _redaction_token()
    scrubbed = scrub_pii(text)
    digit_run = re.compile(rf"(?<!\d)\d(?:[ .\-]?\d){{{min_digits - 1},}}(?!\d)")
    return digit_run.sub(redaction, scrubbed)


def _redaction_token() -> str:
    return str(load_config("guardrails").get("redaction_token", DEFAULT_REDACTION))
