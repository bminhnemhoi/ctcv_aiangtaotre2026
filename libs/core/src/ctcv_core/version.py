"""Version information for ctcv-core."""

from importlib import metadata

__version__ = "0.1.0"
DISTRIBUTION_NAME = "ctcv-core"


def get_version() -> str:
    """Return the installed distribution version, falling back to ``__version__``."""
    try:
        return metadata.version(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return __version__
