from pathlib import Path

from sqlalchemy import inspect

from video_pose.migration import upgrade_database
from video_pose.sql_repository import SQLAlchemySessionRepository


def test_alembic_upgrade_creates_repository_schema(
    tmp_path: Path,
) -> None:
    database = tmp_path / "migration.db"
    url = f"sqlite:///{database}"
    upgrade_database(url)

    repository = SQLAlchemySessionRepository(url)
    table_names = set(inspect(repository.engine).get_table_names())
    assert {
        "alembic_version",
        "vp_sessions",
        "vp_actions",
        "vp_steps",
        "vp_violations",
    }.issubset(table_names)
