from pathlib import Path

from video_pose.reindex import reindex_session
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)
from video_pose.sql_repository import SQLAlchemySessionRepository


def test_reindex_restores_violation_review_by_stable_identity(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    writer = SessionAuditWriter(audit_root)
    metadata = SessionAuditMetadata(
        session_id="reindex-review",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "reindex-review",
        {
            "actions": [],
            "rule_updates": [
                {
                    "new_violations": [
                        {
                            "rule_id": "R1",
                            "step": "S010",
                            "type": "SPATIAL",
                            "severity": "MAJOR",
                            "event_id": "a1",
                            "confidence": 0.9,
                        }
                    ],
                    "changed_steps": [],
                }
            ],
        },
    )
    writer.append_review(
        "reindex-review",
        {
            "rule_id": "R1",
            "step_code": "S010",
            "event_id": "a1",
            "reviewer": "reviewer-1",
            "reviewed_at": "2026-09-21T00:02:00+00:00",
            "review": {
                "decision": "DISMISSED",
                "comment": "遮挡导致误报",
            },
        },
    )

    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'reindex-review.db'}"
    )
    repository.create_schema()
    result = reindex_session(directory, repository)
    assert result.review_count == 1

    stored = repository.get_session("reindex-review")
    assert stored is not None
    assert stored["violations"][0]["review_status"] == "DISMISSED"
    assert stored["violations"][0]["reviewed_by"] == "reviewer-1"
