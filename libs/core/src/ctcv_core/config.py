"""Configuration loading with JSON Schema validation and environment overrides.

``load_config("app")`` reads ``config/app.yaml`` from the repository root, applies
``CTCV_APP_<KEY>=value`` overrides for top-level scalar keys, validates the result
against ``config/schemas/app.schema.json`` (JSON Schema 2020-12) and caches it.
"""

from __future__ import annotations

import copy
import json
import os
import tomllib
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ctcv_core.errors import AppError

ENV_PREFIX = "CTCV"
REPO_ROOT_ENV = "CTCV_REPO_ROOT"
CONFIG_DIRNAME = "config"
SCHEMAS_DIRNAME = "schemas"
_MAX_ERRORS_SHOWN = 5
_TRUE_WORDS = frozenset({"1", "true", "yes", "on", "có"})
_FALSE_WORDS = frozenset({"0", "false", "no", "off", "không"})

_cache: dict[str, dict[str, Any]] = {}


class ConfigError(AppError):
    """Raised when a config file, its schema or an override is invalid."""

    def __init__(self, message_vi: str, details: dict[str, Any] | None = None) -> None:
        """Create a CONFIG_ERROR (HTTP 500) with a Vietnamese message."""
        super().__init__("CONFIG_ERROR", message_vi, 500, details)


def _is_workspace_root(directory: Path) -> bool:
    """Return True when ``directory/pyproject.toml`` declares ``[tool.uv.workspace]``."""
    pyproject = directory / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return False
    return "workspace" in data.get("tool", {}).get("uv", {})


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the uv workspace root by walking up from ``start`` (default: this file).

    The ``CTCV_REPO_ROOT`` environment variable, when set, wins.

    Raises:
        ConfigError: when no ``pyproject.toml`` with ``[tool.uv.workspace]`` is found.
    """
    override = os.environ.get(REPO_ROOT_ENV)
    if override:
        root = Path(override).expanduser().resolve()
        if _is_workspace_root(root):
            return root
        raise ConfigError(
            f"Biến {REPO_ROOT_ENV} trỏ tới thư mục không phải gốc kho mã: {root}",
            {"path": str(root)},
        )
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if _is_workspace_root(candidate):
            return candidate
    raise ConfigError(
        "Không tìm thấy gốc kho mã (pyproject.toml có [tool.uv.workspace]) "
        f"khi đi ngược từ {here}.",
        {"start": str(here)},
    )


def config_path(name: str, root: Path | None = None) -> Path:
    """Return ``<root>/config/<name>.yaml``."""
    return (root or find_repo_root()) / CONFIG_DIRNAME / f"{name}.yaml"


def schema_path(name: str, root: Path | None = None) -> Path:
    """Return ``<root>/config/schemas/<name>.schema.json``."""
    return (root or find_repo_root()) / CONFIG_DIRNAME / SCHEMAS_DIRNAME / f"{name}.schema.json"


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Thiếu file cấu hình: {path}", {"path": str(path)})
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"File cấu hình {path.name} sai cú pháp YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"File cấu hình {path.name} phải là một bảng khóa–giá trị ở cấp cao nhất.",
            {"path": str(path)},
        )
    return data


def _read_schema(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Thiếu JSON Schema cho cấu hình: {path}", {"path": str(path)})
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Schema {path.name} không phải JSON hợp lệ: {exc}") from exc
    Draft202012Validator.check_schema(schema)
    return schema


def _coerce(raw: str, current: Any, env_key: str) -> Any:
    """Convert ``raw`` to the type of ``current`` (bool, int, float, str or None)."""
    if isinstance(current, bool):
        word = raw.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
        raise ConfigError(f"Biến {env_key} phải là true/false, nhận được: {raw!r}")
    if isinstance(current, int):
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"Biến {env_key} phải là số nguyên, nhận được: {raw!r}") from exc
    if isinstance(current, float):
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigError(f"Biến {env_key} phải là số thực, nhận được: {raw!r}") from exc
    return raw


def _apply_env_overrides(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Apply ``CTCV_<NAME>_<KEY>`` overrides for top-level scalar keys, in place."""
    prefix = f"{ENV_PREFIX}_{name.upper().replace('-', '_')}_"
    by_upper = {str(key).upper(): key for key in data}
    for env_key, raw in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        key = by_upper.get(env_key[len(prefix) :].upper())
        if key is None:
            continue
        current = data[key]
        if isinstance(current, dict | list):
            raise ConfigError(
                f"Biến {env_key} không ghi đè được khóa '{key}' "
                "vì đây không phải giá trị vô hướng.",
                {"key": key},
            )
        data[key] = _coerce(raw, current, env_key)
    return data


def _format_error(error: ValidationError) -> str:
    location = "/".join(str(part) for part in error.absolute_path) or "(gốc)"
    return f"{location}: {error.message}"


def validate_against_schema(data: Any, schema: dict[str, Any], label: str) -> None:
    """Validate ``data`` with JSON Schema 2020-12; raise ``ConfigError`` listing problems."""
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    shown = [_format_error(e) for e in errors[:_MAX_ERRORS_SHOWN]]
    hidden = len(errors) - _MAX_ERRORS_SHOWN
    more = f" (và {hidden} lỗi khác)" if hidden > 0 else ""
    raise ConfigError(
        f"Cấu hình '{label}' không khớp schema{more}: " + "; ".join(shown),
        {"label": label, "errors": [_format_error(e) for e in errors]},
    )


def load_config(name: str, *, root: Path | None = None, reload: bool = False) -> dict[str, Any]:
    """Load, override, validate and cache ``config/<name>.yaml``; return a deep copy.

    Args:
        name: File stem, e.g. ``"app"`` for ``config/app.yaml``.
        root: Repository root override (tests); defaults to :func:`find_repo_root`.
        reload: Bypass the cache and re-read from disk.
    """
    repo_root = root or find_repo_root()
    cache_key = f"{repo_root}::{name}"
    if not reload and cache_key in _cache:
        return copy.deepcopy(_cache[cache_key])
    data = _read_yaml_mapping(config_path(name, repo_root))
    data = _apply_env_overrides(data, name)
    validate_against_schema(data, _read_schema(schema_path(name, repo_root)), name)
    _cache[cache_key] = data
    return copy.deepcopy(data)


def clear_config_cache() -> None:
    """Drop every cached config (used by tests and hot reload)."""
    _cache.clear()
