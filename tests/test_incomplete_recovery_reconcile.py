from pathlib import Path

from video_pose.incomplete_recovery import (
    IncompleteRecoveryRequest,
    recover_incomplete_audit_session,
)
from video_pose.persistence_reconcile import reconcile_audit_root
from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)
from video_pose.sql_repository import SQLAlchemySessionRepository


def test_recovered_incomplete_session_reindexes_as_aborted(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    writer = SessionAuditWriter(audit_root)
    metadata = SessionAuditMetadata(
        session_id="crashed-db",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload(
        "crashed-db",
        {
            "timestamp_ms": 500,
            "actions": [],
            "rule_updates": [],
        },
    )
    recover_incomplete_audit_session(
        directory,
        IncompleteRecoveryRequest(reason="process crash"),
        recovered_by="engineer-1",
    )

    repository = SQLAlchemySessionRepository(
        f"sqlite:///{tmp_path / 'recovered.db'}"
    )
    repository.create_schema()
    report = reconcile_audit_root(
        audit_root,
        repository,
    )
    assert report.repaired_count == 1
    stored = repository.get_session("crashed-db")
    assert stored is not None
    assert stored["session"]["status"] == "ABORTED"
    assert stored["session"]["passed"] is False
    assert stored["violations"][0]["rule_id"] == (
        "SYSTEM-QUALITY-RECOVERY"
    )
