"""Time-to-live helpers for screenshots (ADR-005: an image lives 60 s in MinIO, then is gone).

All arithmetic happens in UTC; naive datetimes are assumed to be UTC already. The default
TTL is ``config/app.yaml: screen_ttl_seconds``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ctcv_core.config import load_config


def default_ttl_seconds() -> int:
    """Return ``screen_ttl_seconds`` from ``config/app.yaml``."""
    return int(load_config("app")["screen_ttl_seconds"])


def as_utc(moment: datetime) -> datetime:
    """Return ``moment`` as an aware UTC datetime (naive input is taken as UTC)."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _check_ttl(ttl_s: float) -> None:
    if ttl_s <= 0:
        raise ValueError(f"TTL phải lớn hơn 0 giây, nhận được: {ttl_s}")


def expires_at(created_at: datetime, ttl_s: float) -> datetime:
    """Return the UTC instant at which an object created at ``created_at`` expires."""
    _check_ttl(ttl_s)
    return as_utc(created_at) + timedelta(seconds=ttl_s)


def is_expired(created_at: datetime, ttl_s: float, *, now: datetime | None = None) -> bool:
    """True once ``now`` (default: current UTC time) is at or past ``created_at + ttl_s``.

    Raises:
        ValueError: when ``ttl_s`` is not positive.
    """
    current = as_utc(now) if now is not None else datetime.now(tz=UTC)
    return current >= expires_at(created_at, ttl_s)


def seconds_left(created_at: datetime, ttl_s: float, *, now: datetime | None = None) -> float:
    """Seconds until expiry, clamped at 0."""
    current = as_utc(now) if now is not None else datetime.now(tz=UTC)
    remaining = (expires_at(created_at, ttl_s) - current).total_seconds()
    return max(0.0, remaining)
