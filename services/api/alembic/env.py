"""Alembic environment for ctcv-api.

The target metadata is ``ctcv_api.models.Base.metadata``; the URL comes from
``ctcv_api.settings.Settings().database_url`` (``DATABASE_URL``) unless the
Alembic config already carries ``sqlalchemy.url`` (tests set it programmatically).
Batch mode is enabled on SQLite so constraint changes work there too.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from ctcv_api.models import Base
from ctcv_api.settings import Settings

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    """Config override first, then ``DATABASE_URL`` from the environment / ``.env``."""
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL without connecting (``alembic upgrade head --sql``)."""
    url = database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection (a caller may pass one via attributes)."""
    connection = config.attributes.get("connection")
    engine = (
        None if connection is not None else create_engine(database_url(), poolclass=pool.NullPool)
    )
    with engine.connect() if engine is not None else _nullcontext(connection) as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            render_as_batch=conn.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


def _nullcontext(value):  # noqa: ANN001, ANN202
    """Tiny stand-in for ``contextlib.nullcontext`` typed for a Connection."""
    from contextlib import nullcontext

    return nullcontext(value)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
