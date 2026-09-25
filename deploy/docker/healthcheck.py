"""Container HEALTHCHECK helper: ``python /app/healthcheck.py <port> [path]``.

Exits 0 when ``http://127.0.0.1:<port><path>`` answers 200 (default path ``/health``,
brief §3). Standard library only, so it works in every python:3.12-slim image.
"""

import sys
import urllib.request


def main() -> int:
    """Probe the local service once and map the outcome to an exit code."""
    port = sys.argv[1] if len(sys.argv) > 1 else "8000"
    path = sys.argv[2] if len(sys.argv) > 2 else "/health"
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=4) as resp:
            return 0 if resp.status == 200 else 1
    except Exception:  # noqa: BLE001 - any failure means unhealthy
        return 1


if __name__ == "__main__":
    sys.exit(main())
