from pathlib import Path

from video_pose.session_audit import SessionAuditMetadata
from video_pose.sql_repository import SQLAlchemySessionRepository
from video_pose.violation_review import ViolationReviewRequest


def _metadata() -> SessionAuditMetadata:
    return SessionAuditMetadata(
        session_id="review-session",
        operator_id="operator-1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )


def _insert_violation(repository: SQLAlchemySessionRepository) -> None:
    repository.start_session(_metadata())
    repository.record_update(
        "review-session",
        {
            "actions": [],
            "rule_updates": [
                {
                    "new_violations": [
                        {
                            "rule_id": "R-WRONG-TOOL",
                            "step": "S030",
                            "type": "WRONG_TOOL",
                            "severity": "MAJOR",
                            "event_id": "a3",
                            "confidence": 0.95,
                        }
                    ],
                    "changed_steps": [],
                }
            ],
        },
    )


def test_repository_supports_violation_review(tmp_path: Path) -> None:
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'review.db'}"
    )
    repository.create_schema()
    _insert_violation(repository)

    pending = repository.list_pending_reviews()
    assert len(pending) == 1
    violation_id = pending[0]["id"]
    assert pending[0]["review_status"] == "UNREVIEWED"

    reviewed = repository.review_violation(
        "review-session",
        violation_id,
        ViolationReviewRequest(
            decision="CONFIRMED",
            reason_code="VIDEO_CONFIRMED",
            comment="四路视频复核确认",
        ),
        reviewer="reviewer-1",
    )
    assert reviewed is not None
    assert reviewed["review_status"] == "CONFIRMED"
    assert reviewed["reviewed_by"] == "reviewer-1"
    assert repository.list_pending_reviews() == []


def test_review_by_stable_identity_supports_reindex(tmp_path: Path) -> None:
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'identity.db'}"
    )
    repository.create_schema()
    _insert_violation(repository)
    reviewed = repository.review_violation_by_identity(
        "review-session",
        rule_id="R-WRONG-TOOL",
        step_code="S030",
        event_id="a3",
        review=ViolationReviewRequest(decision="DISMISSED"),
        reviewer="reviewer-2",
    )
    assert reviewed is not None
    assert reviewed["review_status"] == "DISMISSED"
