from pathlib import Path

from video_pose.persistence_reconcile import (
    inspect_session_consistency,
    reconcile_audit_root,
)
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)
from video_pose.sql_repository import SQLAlchemySessionRepository


def _write_completed_audit(root: Path) -> Path:
    writer = SessionAuditWriter(root)
    metadata = SessionAuditMetadata(
        session_id="reconcile-s1",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "reconcile-s1",
        {
            "actions": [
                {
                    "event_id": "a1",
                    "sequence": 1,
                    "action": "PICK",
                    "started_at_ms": 100,
                    "confidence": 0.9,
                }
            ],
            "rule_updates": [],
        },
    )
    writer.append_payload(
        "reconcile-s1",
        {
            "actions": [
                {
                    "event_id": "a2",
                    "sequence": 2,
                    "action": "PLACE",
                    "started_at_ms": 200,
                    "confidence": 0.9,
                }
            ],
            "rule_updates": [],
        },
    )
    writer.finish(
        "reconcile-s1",
        {
            "result": {
                "session_id": "reconcile-s1",
                "operation": "assembly",
                "rule_set_version": 1,
                "steps": [],
                "violations": [],
                "score": 100.0,
                "passed": True,
            },
            "new_violations": [],
            "changed_steps": [],
        },
        status="COMPLETED",
    )
    return directory


def test_reconcile_repairs_missing_completed_session(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    directory = _write_completed_audit(audit_root)
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'query.db'}"
    )
    repository.create_schema()

    before = inspect_session_consistency(
        directory,
        repository,
    )
    assert before.consistent is False

    report = reconcile_audit_root(
        audit_root,
        repository,
    )
    assert report.repaired_count == 1
    assert report.failed_count == 0

    after = inspect_session_consistency(
        directory,
        repository,
    )
    assert after.consistent is True
    stored = repository.get_session("reconcile-s1")
    assert stored is not None
    assert [item["event_id"] for item in stored["actions"]] == [
        "a1",
        "a2",
    ]


def test_reconcile_repairs_completed_session_with_missing_updates(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    directory = _write_completed_audit(audit_root)
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'partial.db'}"
    )
    repository.create_schema()

    metadata = SessionAuditMetadata.model_validate_json(
        (directory / "metadata.json").read_text(encoding="utf-8")
    )
    repository.start_session(metadata)
    repository.record_update(
        "reconcile-s1",
        {
            "actions": [
                {
                    "event_id": "a1",
                    "sequence": 1,
                    "action": "PICK",
                    "started_at_ms": 100,
                    "confidence": 0.9,
                }
            ],
            "rule_updates": [],
        },
    )
    repository.finalize(
        "reconcile-s1",
        {
            "result": {
                "steps": [],
                "violations": [],
                "score": 100.0,
                "passed": True,
            }
        },
        status="COMPLETED",
    )

    before = inspect_session_consistency(
        directory,
        repository,
    )
    assert "action identity set mismatch" in before.reasons

    report = reconcile_audit_root(audit_root, repository)
    assert report.repaired_count == 1
    after = inspect_session_consistency(directory, repository)
    assert after.consistent is True


def test_second_reconcile_is_idempotent_skip(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    _write_completed_audit(audit_root)
    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'idempotent.db'}"
    )
    repository.create_schema()

    first = reconcile_audit_root(audit_root, repository)
    second = reconcile_audit_root(audit_root, repository)
    assert first.repaired_count == 1
    assert second.repaired_count == 0
    assert second.skipped_count == 1
