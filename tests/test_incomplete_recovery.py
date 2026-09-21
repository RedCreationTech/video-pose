import json
from pathlib import Path

from video_pose.incomplete_recovery import (
    IncompleteRecoveryRequest,
    list_incomplete_audit_sessions,
    recover_incomplete_audit_session,
)
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)


def _incomplete(root: Path) -> Path:
    writer = SessionAuditWriter(root)
    metadata = SessionAuditMetadata(
        session_id="crashed-s1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=4,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "crashed-s1",
        {
            "timestamp_ms": 1200,
            "actions": [],
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
                    "score": 90,
                    "passed": False,
                }
            ],
        },
    )
    return directory


def test_incomplete_session_recovery_preserves_state_and_aborts(
    tmp_path: Path,
) -> None:
    directory = _incomplete(tmp_path)
    before = list_incomplete_audit_sessions(tmp_path)
    assert [item.session_id for item in before] == ["crashed-s1"]

    result = recover_incomplete_audit_session(
        directory,
        IncompleteRecoveryRequest(
            reason="edge host lost power"
        ),
        recovered_by="engineer-1",
    )
    assert result.final_status == "ABORTED"
    assert result.last_timestamp_ms == 1200
    assert result.retained_violation_count == 1
    assert result.retained_step_count == 1

    final = json.loads(
        (directory / "final.json").read_text(encoding="utf-8")
    )
    assert final["status"] == "ABORTED"
    result_payload = final["result"]["result"]
    assert result_payload["passed"] is False
    assert result_payload["score"] == 0.0
    assert [item["rule_id"] for item in result_payload["violations"]] == [
        "R1",
        "SYSTEM-QUALITY-RECOVERY",
    ]

    recovery = json.loads(
        (directory / "recovery.json").read_text(encoding="utf-8")
    )
    assert recovery["recovered_by"] == "engineer-1"
    assert recovery["reason"] == "edge host lost power"
    assert list_incomplete_audit_sessions(tmp_path) == []
