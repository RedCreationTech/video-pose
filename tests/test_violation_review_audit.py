import json
from pathlib import Path

from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)


def test_review_is_appended_to_immutable_audit(tmp_path: Path) -> None:
    writer = SessionAuditWriter(tmp_path)
    metadata = SessionAuditMetadata(
        session_id="audit-review",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_review(
        "audit-review",
        {
            "rule_id": "R1",
            "step_code": "S010",
            "event_id": "a1",
            "reviewer": "reviewer-1",
            "reviewed_at": "2026-09-21T00:01:00+00:00",
            "review": {
                "decision": "CONFIRMED",
                "reason_code": "VIDEO_CONFIRMED",
            },
        },
    )
    records = (directory / "reviews.jsonl").read_text(
        encoding="utf-8"
    ).strip().splitlines()
    assert len(records) == 1
    payload = json.loads(records[0])["payload"]
    assert payload["review"]["decision"] == "CONFIRMED"
