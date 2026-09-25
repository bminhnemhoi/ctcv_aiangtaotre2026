"""Runtime settings for the API, read from the environment and ``.env``.

Variable names match ``.env.example``. Threshold defaults (JWT TTL, rate limit,
session cap, screenshot TTL, log retention, ports) come from ``config/app.yaml``
so nothing operational is hard-coded here. Tests build
``Settings(_env_file=None, ...)`` to stay independent of a developer's ``.env``.

The optional demo secrets (``CTCV_DEMO_QR_TOKEN``, ``CTCV_DEMO_STAFF_PASSWORD``) switch on
the demo join/login of ADR-007; they are refused in ``prod`` and never echoed in errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ctcv_core.config import load_config

DEV_JWT_SECRET = "dev-only-change-me-not-for-production-use"
WEAK_SECRETS = frozenset({"", "CHANGE_ME", DEV_JWT_SECRET})
DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./ctcv-dev.db"
PROD_ENV = "prod"
# Spellings of the production environment accepted from the environment (red-team F-07:
# "production", "PROD", " Prod " used to slip past the prod-only refusals).
PROD_ALIASES = frozenset({"prod", "production"})
LOCAL_DOMAINS = frozenset({"", "localhost", "127.0.0.1"})
# Minimum lengths of the demo secrets (ADR-007 C6, C10).
DEMO_QR_TOKEN_MIN = 16
DEMO_PASSWORD_MIN = 12


def _app(key: str) -> Any:
    """Read one top-level key of ``config/app.yaml`` (validated, cached by ctcv_core)."""
    return load_config("app")[key]


class Settings(BaseSettings):
    """Environment-backed settings (see ``.env.example`` for every variable)."""

    # hide_input_in_errors: a failed validation must never print a secret it was given.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    ctcv_env: str = Field(
        default_factory=lambda: str(_app("env")),
        description="Môi trường chạy: dev | staging | prod",
    )
    log_level: str = Field(default="INFO", description="Mức log (INFO, DEBUG, WARNING...)")
    api_host: str = Field(default="0.0.0.0", description="Địa chỉ uvicorn lắng nghe")
    api_port: int = Field(
        default_factory=lambda: int(_app("ports")["api"]),
        description="Cổng API (mặc định config/app.yaml: ports.api)",
    )

    database_url: str = Field(
        default=DEFAULT_DATABASE_URL, description="Chuỗi kết nối SQLAlchemy (prod: PostgreSQL)"
    )
    redis_url: str | None = Field(default=None, description="redis://host:port/db; trống = bỏ qua")
    qdrant_url: str | None = Field(default=None, description="http://host:6333; trống = bỏ qua")
    minio_endpoint: str | None = Field(default=None, description="host:port của MinIO")
    minio_access_key: str | None = Field(default=None, description="Khóa truy cập MinIO")
    minio_secret_key: SecretStr | None = Field(default=None, description="Khóa bí mật MinIO")
    minio_bucket_screens: str = Field(
        default="screens", description="Bucket ảnh màn hình (TTL 60 s)"
    )

    jwt_secret: SecretStr = Field(
        default=SecretStr(DEV_JWT_SECRET), description="Khóa ký JWT HS256 (bắt buộc đổi ở prod)"
    )
    jwt_ttl_minutes: int = Field(
        default_factory=lambda: int(_app("jwt_ttl_minutes")), gt=0, description="Hạn token (phút)"
    )
    rate_limit_per_min: int = Field(
        default_factory=lambda: int(_app("rate_limit_per_min")),
        ge=0,
        description="Số yêu cầu tối đa mỗi phút mỗi thiết bị (0 = tắt)",
    )
    max_concurrent_sessions: int = Field(
        default_factory=lambda: int(_app("max_concurrent_sessions")),
        ge=1,
        description="Số phiên sandbox đồng thời tối đa",
    )
    screen_ttl_seconds: int = Field(
        default_factory=lambda: int(_app("screen_ttl_seconds")),
        ge=1,
        description="Thời gian giữ ảnh màn hình trong MinIO (giây)",
    )
    log_retention_days: int = Field(
        default_factory=lambda: int(_app("log_retention_days")),
        ge=1,
        description="Số ngày giữ log ứng dụng",
    )

    app_domain: str = Field(default="localhost", description="Tên miền công khai (HTTPS qua Caddy)")
    cors_origins: str | None = Field(
        default=None, description="Danh sách origin CORS, phân cách bằng dấu phẩy (ghi đè suy luận)"
    )
    scenarios_dir: Path | None = Field(
        default=None, description="Ghi đè thư mục kịch bản sandbox (dùng trong test)"
    )
    health_timeout_s: float = Field(
        default=1.5, gt=0, description="Thời gian chờ tối đa mỗi kiểm tra trong /health (giây)"
    )

    ctcv_demo_qr_token: SecretStr | None = Field(
        default=None,
        description=f"Mã QR lớp demo (≥ {DEMO_QR_TOKEN_MIN} ký tự); trống = tắt demo; cấm ở prod",
    )
    ctcv_demo_staff_password: SecretStr | None = Field(
        default=None,
        description=(
            f"Mật khẩu cán bộ demo (≥ {DEMO_PASSWORD_MIN} ký tự); trống = tắt demo; cấm ở prod"
        ),
    )

    @field_validator("ctcv_env", mode="after")
    @classmethod
    def _normalise_env(cls, value: str) -> str:
        """Case- and space-insensitive environment name; "production" means ``prod``."""
        folded = value.strip().casefold()
        return PROD_ENV if folded in PROD_ALIASES else folded

    @field_validator("ctcv_demo_qr_token", "ctcv_demo_staff_password", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: Any) -> Any:
        """Treat an empty or blank variable (as in ``.env.example``) as "demo off"."""
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str) and not raw.strip():
            return None
        return value

    @model_validator(mode="after")
    def _reject_weak_secret_in_prod(self) -> Settings:
        """Refuse to start in ``prod`` with a placeholder JWT secret."""
        if self.ctcv_env == PROD_ENV and self.jwt_secret.get_secret_value() in WEAK_SECRETS:
            raise ValueError(
                "JWT_SECRET chưa được đặt cho môi trường prod "
                "(không dùng giá trị mặc định hoặc CHANGE_ME)."
            )
        return self

    @model_validator(mode="after")
    def _check_demo_mode(self) -> Settings:
        """Refuse demo secrets in ``prod`` and demo secrets that are too short (ADR-007 C6)."""
        token, password = self.ctcv_demo_qr_token, self.ctcv_demo_staff_password
        if self.ctcv_env == PROD_ENV and (token is not None or password is not None):
            raise ValueError(
                "Không được bật chế độ demo ở môi trường prod: bỏ CTCV_DEMO_QR_TOKEN và "
                "CTCV_DEMO_STAFF_PASSWORD rồi khởi động lại."
            )
        demo_on = token is not None or password is not None
        if demo_on and self.jwt_secret.get_secret_value() in WEAK_SECRETS:
            # Red-team F-08: the default secret is public in the code, so anyone could sign
            # an officer token while the demo login is on.
            raise ValueError(
                "Bật chế độ demo thì phải đặt JWT_SECRET riêng (không dùng giá trị mặc định)."
            )
        if token is not None and len(token.get_secret_value()) < DEMO_QR_TOKEN_MIN:
            raise ValueError(f"CTCV_DEMO_QR_TOKEN phải dài ít nhất {DEMO_QR_TOKEN_MIN} ký tự.")
        if password is not None and len(password.get_secret_value()) < DEMO_PASSWORD_MIN:
            raise ValueError(
                f"CTCV_DEMO_STAFF_PASSWORD phải dài ít nhất {DEMO_PASSWORD_MIN} ký tự."
            )
        return self

    @property
    def is_sqlite(self) -> bool:
        """True when ``database_url`` points at SQLite (dev/tests)."""
        return self.database_url.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins: ``CORS_ORIGINS`` if set, else derived from app.yaml + domain."""
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        web_port = int(_app("ports")["web"])
        origins = [f"http://localhost:{web_port}", f"http://127.0.0.1:{web_port}"]
        if self.app_domain not in LOCAL_DOMAINS:
            origins.append(f"https://{self.app_domain}")
        return origins


def get_settings() -> Settings:
    """Build settings from the process environment and ``.env``."""
    return Settings()
