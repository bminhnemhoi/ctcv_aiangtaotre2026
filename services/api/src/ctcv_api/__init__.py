"""CTCV API service (distribution ``ctcv-api``, import ``ctcv_api``).

FastAPI application factory (:func:`ctcv_api.main.create_app`), JWT auth, request and
response schemas (brief §3), SQLAlchemy models for the nine tables (brief §4) and the
Alembic migrations that keep them in step.
"""

from importlib import metadata

__version__ = "0.1.0"
DISTRIBUTION_NAME = "ctcv-api"


def get_version() -> str:
    """Return the installed distribution version, falling back to ``__version__``."""
    try:
        return metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return __version__
