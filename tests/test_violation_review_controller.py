import json
from pathlib import Path
from types import SimpleNamespace

from video_pose.persistent_session_controller import (
    PersistentLiveSessionController,
)
from video_pose.runtime_config import load_analysis_config
from video_pose.session_audit import SessionAuditMetadata
from video_pose.sql_repository import SQLAlchemySessionRepository
from video_pose.violation_review import ViolationReviewRequest


def test_controller_reviews_violation_and_audits_it(
    tmp_path: Path,
) -> None:
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'reviews.db'}"
    )
    repository.create_schema()

    controller = PersistentLiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        hub=SimpleNamespace(),
        audit_root=tmp_path / "audit",
        repository=repository,
    )
    metadata = SessionAuditMetadata(
        session_id="review-controller",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    controller.audit.start(metadata)
    repository.start_session(metadata)
    repository.record_update(
        "review-controller",
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
    violation = repository.list_pending_reviews()[0]

    result = controller.review_violation(
        "review-controller",
        violation["id"],
        ViolationReviewRequest(
            decision="CONFIRMED",
            comment="video review confirmed",
        ),
        reviewer="reviewer-1",
    )
    assert result["review_status"] == "CONFIRMED"

    records = (
        tmp_path
        / "audit"
        / "review-controller"
        / "reviews.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(records[0])["payload"]
    assert payload["rule_id"] == "R1"
    assert payload["reviewer"] == "reviewer-1"
