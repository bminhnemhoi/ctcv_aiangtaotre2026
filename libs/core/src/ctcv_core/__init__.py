"""ctcv-core: shared building blocks for every CTCV service.

Everything here is side-effect free at import time except ``ctcv_core.paths``,
which resolves the repository root once.
"""

from ctcv_core.config import ConfigError, clear_config_cache, find_repo_root, load_config
from ctcv_core.errors import (
    AppError,
    Forbidden,
    NotFound,
    NotImplementedYet,
    ValidationFailed,
)
from ctcv_core.version import __version__, get_version

__all__ = [
    "AppError",
    "ConfigError",
    "Forbidden",
    "NotFound",
    "NotImplementedYet",
    "ValidationFailed",
    "__version__",
    "clear_config_cache",
    "find_repo_root",
    "get_version",
    "load_config",
]
