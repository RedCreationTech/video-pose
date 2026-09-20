from pathlib import Path

from video_pose.session_audit import SessionAuditMetadata
from video_pose.sql_repository import SQLAlchemySessionRepository


def _metadata() -> SessionAuditMetadata:
    return SessionAuditMetadata(
        session_id="db-session-1",
        operator_id="operator-1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=3,
        started_at="2026-09-20T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )


def test_repository_persists_session_actions_steps_and_violations(
    tmp_path: Path,
) -> None:
    database = tmp_path / "video-pose.db"
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{database}"
    )
    repository.create_schema()
    repository.start_session(_metadata())

    repository.record_update(
        "db-session-1",
        {
            "actions": [
                {
                    "event_id": "a1",
                    "sequence": 1,
                    "action": "PICK",
                    "object": {"class": "component_A"},
                    "source_zone": "bin",
                    "started_at_ms": 100,
                    "confidence": 0.95,
                }
            ],
            "rule_updates": [
                {
                    "changed_steps": [
                        {
                            "code": "S010",
                            "state": "COMPLETED",
                            "event_id": "a1",
                            "confidence": 0.95,
                        }
                    ],
                    "new_violations": [
                        {
                            "rule_id": "R1",
                            "step": "S010",
                            "type": "TEMPORAL",
                            "severity": "MINOR",
                            "event_id": "a1",
                            "confidence": 0.95,
                        }
                    ],
                    "score": 98.0,
                    "passed": True,
                }
            ],
        },
    )

    repository.finalize(
        "db-session-1",
        {
            "result": {
                "score": 98.0,
                "passed": True,
                "steps": [
                    {
                        "code": "S010",
                        "state": "COMPLETED",
                        "event_id": "a1",
                        "confidence": 0.95,
                    }
                ],
                "violations": [],
            }
        },
        status="COMPLETED",
    )

    payload = repository.get_session("db-session-1")
    assert payload is not None
    assert payload["session"]["status"] == "COMPLETED"
    assert payload["session"]["final_score"] == 98.0
    assert len(payload["actions"]) == 1
    assert len(payload["violations"]) == 1
    assert payload["steps"][0]["state"] == "COMPLETED"

    listed = repository.list_sessions()
    assert listed[0]["session_id"] == "db-session-1"


def test_repository_update_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{database}"
    )
    repository.create_schema()
    repository.start_session(_metadata())
    payload = {
        "actions": [
            {
                "event_id": "a1",
                "sequence": 1,
                "action": "PICK",
                "started_at_ms": 10,
            }
        ],
        "rule_updates": [],
    }
    repository.record_update("db-session-1", payload)
    repository.record_update("db-session-1", payload)

    stored = repository.get_session("db-session-1")
    assert stored is not None
    assert len(stored["actions"]) == 1
