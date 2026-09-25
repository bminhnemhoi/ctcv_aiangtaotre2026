from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ctcv_core.config import load_config
from ctcv_vision.ttl import as_utc, default_ttl_seconds, expires_at, is_expired, seconds_left

T0 = datetime(2026, 9, 18, 8, 0, 0, tzinfo=UTC)


def test_default_ttl_comes_from_app_yaml():
    assert default_ttl_seconds() == load_config("app")["screen_ttl_seconds"]
    assert default_ttl_seconds() == 60


def test_is_expired_around_the_boundary():
    ttl = default_ttl_seconds()
    assert is_expired(T0, ttl, now=T0) is False
    assert is_expired(T0, ttl, now=T0 + timedelta(seconds=ttl - 1)) is False
    assert is_expired(T0, ttl, now=T0 + timedelta(seconds=ttl)) is True
    assert is_expired(T0, ttl, now=T0 + timedelta(hours=1)) is True


def test_naive_datetimes_are_treated_as_utc():
    naive = T0.replace(tzinfo=None)
    assert expires_at(naive, 60) == T0 + timedelta(seconds=60)
    assert is_expired(naive, 60, now=naive + timedelta(seconds=60)) is True
    assert as_utc(naive) == T0


def test_other_timezones_are_converted():
    hanoi = timezone(timedelta(hours=7))
    created_in_hanoi = T0.astimezone(hanoi)
    assert expires_at(created_in_hanoi, 60) == T0 + timedelta(seconds=60)
    assert is_expired(created_in_hanoi, 60, now=T0 + timedelta(seconds=59)) is False


def test_seconds_left_clamps_at_zero():
    assert seconds_left(T0, 60, now=T0 + timedelta(seconds=15)) == 45.0
    assert seconds_left(T0, 60, now=T0 + timedelta(seconds=90)) == 0.0
    assert seconds_left(T0, 0.5, now=T0) == 0.5


def test_now_defaults_to_current_time():
    assert is_expired(datetime.now(tz=UTC), 3600) is False
    assert is_expired(datetime.now(tz=UTC) - timedelta(days=1), 1) is True
    assert seconds_left(datetime.now(tz=UTC), 3600) > 3500


@pytest.mark.parametrize("ttl", [0, -1, -0.5])
def test_non_positive_ttl_is_rejected(ttl: float):
    with pytest.raises(ValueError, match="TTL"):
        is_expired(T0, ttl, now=T0)
    with pytest.raises(ValueError):
        expires_at(T0, ttl)
