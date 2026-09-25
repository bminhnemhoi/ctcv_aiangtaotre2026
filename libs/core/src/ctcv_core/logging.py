"""JSON logging with request-id propagation and PII scrubbing.

Usage::

    from ctcv_core.logging import request_id_var, setup_logging
    log = setup_logging("api")
    request_id_var.set("req-123")
    log.info("session started", extra={"session_id": "..."})

Every record becomes one JSON line with ``ts``, ``level``, ``logger``, ``msg``,
``request_id`` and ``extra``; the :class:`PiiScrubFilter` replaces CCCD numbers,
card numbers, OTP codes, phone numbers and e-mails with ``[ĐÃ CHE]`` using the
regexes declared in ``config/guardrails.yaml``.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import IO, Any

from ctcv_core.config import load_config

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctcv_request_id", default=None
)

DEFAULT_REDACTION = "[ĐÃ CHE]"
REDACTED_PLACEHOLDER = "{redacted}"
LOG_LEVEL_ENV = "LOG_LEVEL"
DEFAULT_LEVEL = "INFO"
_HANDLER_MARK = "_ctcv_handler"

PiiPatterns = list[tuple[re.Pattern[str], str]]

_STANDARD_ATTRS = frozenset(
    {
        *logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None).__dict__,
        "message",
        "asctime",
        "taskName",
    }
)


def load_pii_patterns(config: Mapping[str, Any] | None = None) -> PiiPatterns:
    """Compile ``pii_patterns`` from ``config/guardrails.yaml`` (or the given mapping)."""
    cfg = config if config is not None else load_config("guardrails")
    token = str(cfg.get("redaction_token", DEFAULT_REDACTION))
    patterns: PiiPatterns = []
    for item in cfg.get("pii_patterns", []):
        replacement = str(item.get("replacement", REDACTED_PLACEHOLDER))
        patterns.append(
            (re.compile(item["regex"]), replacement.replace(REDACTED_PLACEHOLDER, token))
        )
    return patterns


def scrub_pii(text: str, patterns: Iterable[tuple[re.Pattern[str], str]] | None = None) -> str:
    """Return ``text`` with every PII pattern replaced by its redaction string."""
    active = list(patterns) if patterns is not None else load_pii_patterns()
    for pattern, replacement in active:
        text = pattern.sub(replacement, text)
    return text


class PiiScrubFilter(logging.Filter):
    """Logging filter that redacts PII in the message and in string ``extra`` fields."""

    def __init__(self, patterns: PiiPatterns | None = None, name: str = "") -> None:
        """Compile patterns from ``config/guardrails.yaml`` unless given explicitly."""
        super().__init__(name)
        self._patterns = patterns if patterns is not None else load_pii_patterns()

    def scrub(self, text: str) -> str:
        """Redact PII in ``text``."""
        return scrub_pii(text, self._patterns)

    def filter(self, record: logging.LogRecord) -> bool:
        """Rewrite the record in place (always keeps it)."""
        try:
            message = record.getMessage()
        except (TypeError, ValueError, KeyError):
            args = record.args if isinstance(record.args, tuple) else (record.args,)
            message = " ".join([str(record.msg), *(str(arg) for arg in args)])
        record.msg = self.scrub(message)
        record.args = ()
        for key, value in list(record.__dict__.items()):
            if key not in _STANDARD_ATTRS and isinstance(value, str):
                setattr(record, key, self.scrub(value))
        return True


class JsonFormatter(logging.Formatter):
    """Format records as single-line JSON objects (UTF-8, non-ASCII preserved)."""

    def __init__(self, service: str | None = None) -> None:
        """Optionally tag every record with ``service``."""
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` to JSON."""
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if self.service:
            payload["service"] = self.service
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and not key.startswith("_")
        }
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    service: str,
    level: int | str | None = None,
    stream: IO[str] | None = None,
    patterns: PiiPatterns | None = None,
) -> logging.Logger:
    """Install a JSON handler with PII scrubbing on the root logger and return a logger.

    Calling it again replaces the handler installed by a previous call, so it is
    safe to use from tests and from every service entry point.

    Args:
        service: Service name written into every record (``api``, ``agent``...).
        level: Log level; defaults to ``$LOG_LEVEL`` or ``INFO``.
        stream: Output stream; defaults to ``sys.stdout``.
        patterns: Pre-compiled PII patterns (defaults to ``config/guardrails.yaml``).
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(JsonFormatter(service))
    handler.addFilter(PiiScrubFilter(patterns))
    root.addHandler(handler)
    root.setLevel(level or os.environ.get(LOG_LEVEL_ENV, DEFAULT_LEVEL))
    return logging.getLogger(service)
