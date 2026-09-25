"""Alembic: upgrade head on a fresh SQLite file, schema matches the models, downgrade base."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from ctcv_api.models import TABLE_NAMES, Base

API_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = API_DIR / "alembic.ini"
SCRIPTS = API_DIR / "alembic"
STRUCTURAL = {
    "add_table",
    "remove_table",
    "add_column",
    "remove_column",
    "add_index",
    "remove_index",
}


def _config(db_file: Path) -> tuple[Config, str]:
    url = f"sqlite+pysqlite:///{db_file.as_posix()}"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(SCRIPTS))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logging"] = False
    return cfg, url


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_single_head_is_0001_init():
    cfg, _ = _config(Path("unused.db"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0001"]
    assert script.get_revision("0001").down_revision is None
    assert (SCRIPTS / "versions" / "0001_init.py").is_file()


def test_upgrade_head_matches_models_then_downgrade_base(tmp_path):
    cfg, url = _config(tmp_path / "migrate.db")

    command.upgrade(cfg, "head")
    assert _tables(url) == set(TABLE_NAMES)

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={"compare_type": True, "render_as_batch": True}
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    structural = [op for op in diff if op[0] in STRUCTURAL]
    assert structural == [], structural

    command.downgrade(cfg, "base")
    assert _tables(url) == set()


def test_upgrade_is_idempotent_on_second_run(tmp_path):
    cfg, url = _config(tmp_path / "twice.db")
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    assert _tables(url) == set(TABLE_NAMES)


def test_offline_sql_mentions_every_table(tmp_path, capsys):
    cfg, _ = _config(tmp_path / "offline.db")
    command.upgrade(cfg, "head", sql=True)
    sql = capsys.readouterr().out
    for table in TABLE_NAMES:
        assert f"CREATE TABLE {table}" in sql, table
