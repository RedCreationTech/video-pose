from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


_ROOT = Path(__file__).resolve().parents[2]
_MIGRATIONS = _ROOT / "migrations"


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(_MIGRATIONS),
    )
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )
    return config


def upgrade_database(database_url: str) -> None:
    command.upgrade(
        build_alembic_config(database_url),
        "head",
    )


def downgrade_database(
    database_url: str,
    revision: str = "-1",
) -> None:
    command.downgrade(
        build_alembic_config(database_url),
        revision,
    )
