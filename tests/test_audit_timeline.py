from pathlib import Path

from video_pose.audit_timeline import build_session_timeline
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)


def test_audit_timeline_reconstructs_key_events(
    tmp_path: Path,
) -> None:
    writer = SessionAuditWriter(tmp_path)
    metadata = SessionAuditMetadata(
        session_id="timeline-s1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="model.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "timeline-s1",
        {
            "timestamp_ms": 100,
            "actions": [
                {
                    "event_id": "a1",
                    "sequence": 1,
                    "action": "PICK",
                    "object": {"class": "tool"},
                    "source_zone": "rack",
                    "target_zone": "work",
                    "confidence": 0.9,
                }
            ],
            "rule_updates": [
                {
                    "new_violations": [
                        {
                            "rule_id": "R1",
                            "step": "S010",
                            "type": "SPATIAL",
                            "severity": "MAJOR",
                            "message": "wrong zone",
                            "event_id": "a1",
                            "confidence": 0.9,
                        }
                    ],
                    "changed_steps": [
                        {
                            "code": "S010",
                            "state": "VIOLATED",
                            "event_id": "a1",
                            "confidence": 0.9,
                        }
                    ],
                }
            ],
        },
    )
    writer.append_payload(
        "timeline-s1",
        {
            "evidence_scheduled": {
                "evidence_id": "e1",
                "rule_id": "R1",
                "step": "S010",
                "event_id": "a1",
            }
        },
    )
    writer.append_review(
        "timeline-s1",
        {
            "rule_id": "R1",
            "step_code": "S010",
            "event_id": "a1",
            "reviewer": "reviewer-1",
            "reviewed_at": "2026-09-21T00:01:00+00:00",
            "review": {
                "decision": "CONFIRMED",
                "comment": "confirmed",
            },
        },
    )
    writer.finish(
        "timeline-s1",
        {
            "result": {
                "steps": [],
                "violations": [],
                "score": 0,
                "passed": False,
            }
        },
        status="COMPLETED",
    )

    timeline = build_session_timeline(directory)
    types = [event.type for event in timeline.events]
    assert types[0] == "SESSION_STARTED"
    assert "ACTION" in types
    assert "VIOLATION" in types
    assert "STEP" in types
    assert "EVIDENCE" in types
    assert "REVIEW" in types
    assert types[-1] == "SESSION_FINISHED"

    rendered = timeline.model_dump_json()
    assert "/tmp/config.yaml" not in rendered
