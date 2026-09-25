"""Routers for the ``/v1`` API (brief §3) plus the system router mounted at root too."""

from fastapi import APIRouter

from ctcv_api.routers import (
    auth,
    classes,
    coach,
    drills,
    reports,
    scenarios,
    sessions,
    speech,
    system,
)

V1_ROUTERS: tuple[APIRouter, ...] = (
    auth.router,
    classes.router,
    reports.router,
    scenarios.router,
    sessions.router,
    speech.router,
    coach.router,
    drills.router,
    system.router,
)

__all__ = ["V1_ROUTERS", "system"]
