from pathlib import Path

from video_pose.reindex import reindex_session
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)
from video_pose.sql_repository import SQLAlchemySessionRepository


def test_reindex_rebuilds_database_from_audit(tmp_path: Path) -> None:
    audit_root = tmp_path / "audit"
    writer = SessionAuditWriter(audit_root)
    metadata = SessionAuditMetadata(
        session_id="reindex-1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-20T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "reindex-1",
        {
            "actions": [
                {
                    "event_id": "a1",
                    "action": "PICK",
                    "sequence": 1,
                    "started_at_ms": 100,
                }
            ],
            "rule_updates": [],
        },
    )
    writer.finish(
        "reindex-1",
        {
            "result": {
                "score": 100.0,
                "passed": True,
                "steps": [],
                "violations": [],
            }
        },
        status="COMPLETED",
    )

    database = tmp_path / "reindex.db"
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{database}"
    )
    repository.create_schema()
    result = reindex_session(directory, repository)

    assert result.update_count == 1
    assert result.finalized is True
    stored = repository.get_session("reindex-1")
    assert stored is not None
    assert len(stored["actions"]) == 1
    assert stored["session"]["status"] == "COMPLETED"
