"""Settings: env names from .env.example, defaults from config/app.yaml, prod guard, CORS."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctcv_api.settings import DEFAULT_DATABASE_URL, DEV_JWT_SECRET, Settings
from ctcv_core.config import find_repo_root, load_config

ENV_EXAMPLE = find_repo_root() / ".env.example"
REQUIRED_ENV_NAMES = {
    "DATABASE_URL",
    "REDIS_URL",
    "QDRANT_URL",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "JWT_SECRET",
    "JWT_TTL_MINUTES",
    "RATE_LIMIT_PER_MIN",
    "MAX_CONCURRENT_SESSIONS",
    "SCREEN_TTL_SECONDS",
    "LOG_RETENTION_DAYS",
}


def test_env_example_declares_every_variable_settings_reads():
    names = set(re.findall(r"^([A-Z_]+)=", ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE))
    assert REQUIRED_ENV_NAMES <= names
    aliases = {field.upper() for field in Settings.model_fields}
    assert REQUIRED_ENV_NAMES <= aliases


def test_defaults_come_from_app_yaml():
    app = load_config("app")
    settings = Settings(_env_file=None)
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.jwt_ttl_minutes == app["jwt_ttl_minutes"]
    assert settings.rate_limit_per_min == app["rate_limit_per_min"]
    assert settings.max_concurrent_sessions == app["max_concurrent_sessions"]
    assert settings.screen_ttl_seconds == app["screen_ttl_seconds"]
    assert settings.log_retention_days == app["log_retention_days"]
    assert settings.api_port == app["ports"]["api"]
    assert settings.ctcv_env == app["env"]
    assert settings.redis_url is None and settings.qdrant_url is None


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("JWT_TTL_MINUTES", "7")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///x.db")
    monkeypatch.setenv("SCENARIOS_DIR", "sandbox/scenarios")
    settings = Settings(_env_file=None)
    assert settings.jwt_ttl_minutes == 7
    assert settings.database_url == "sqlite+pysqlite:///x.db"
    assert settings.scenarios_dir == Path("sandbox/scenarios")


def test_prod_refuses_placeholder_secret():
    for weak in (DEV_JWT_SECRET, "CHANGE_ME", ""):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, ctcv_env="prod", jwt_secret=weak)


def test_prod_accepts_real_secret():
    settings = Settings(
        _env_file=None, ctcv_env="prod", jwt_secret="a-real-32-char-secret-value-xyz"
    )
    assert settings.ctcv_env == "prod"


def test_dev_tolerates_default_secret():
    assert Settings(_env_file=None).jwt_secret.get_secret_value() == DEV_JWT_SECRET


def test_secret_is_hidden_in_repr():
    settings = Settings(
        _env_file=None,
        jwt_secret="super-secret-value-32-bytes-long!",
        minio_secret_key="minio-secret",
    )
    assert "super-secret-value" not in repr(settings)
    assert "minio-secret" not in repr(settings)


def test_cors_derived_from_web_port_and_domain():
    web = load_config("app")["ports"]["web"]
    assert Settings(_env_file=None).cors_origin_list == [
        f"http://localhost:{web}",
        f"http://127.0.0.1:{web}",
    ]
    with_domain = Settings(_env_file=None, app_domain="ctcv.example.vn").cors_origin_list
    assert with_domain[-1] == "https://ctcv.example.vn"


def test_cors_explicit_list_wins():
    settings = Settings(_env_file=None, cors_origins=" https://a.vn, https://b.vn ,")
    assert settings.cors_origin_list == ["https://a.vn", "https://b.vn"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("jwt_ttl_minutes", 0), ("rate_limit_per_min", -1), ("screen_ttl_seconds", 0)],
)
def test_thresholds_are_range_checked(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_is_sqlite():
    assert Settings(_env_file=None).is_sqlite
    assert not Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/db").is_sqlite
