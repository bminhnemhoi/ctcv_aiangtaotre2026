from __future__ import annotations

import re

import ctcv_core
from ctcv_core import version


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", ctcv_core.__version__)


def test_get_version_matches_installed_or_fallback(monkeypatch) -> None:
    assert version.get_version() == ctcv_core.__version__
    monkeypatch.setattr(version, "DISTRIBUTION_NAME", "ctcv-does-not-exist")
    assert version.get_version() == version.__version__
