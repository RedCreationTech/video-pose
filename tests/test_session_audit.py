import json
from pathlib import Path

from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)


def test_session_audit_writes_metadata_updates_and_final(
    tmp_path: Path,
) -> None:
    writer = SessionAuditWriter(tmp_path)
    metadata = SessionAuditMetadata(
        session_id="s1",
        operator_id="op1",
        operation="assembly",
        workstation_id="ws1",
        rule_set_version=1,
        started_at="2026-09-20T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )
    directory = writer.start(metadata)
    writer.append_payload("s1", {"actions": [{"action": "PICK"}]})
    writer.finish(
        "s1",
        {"score": 100},
        status="COMPLETED",
    )

    assert (directory / "metadata.json").exists()
    updates = (directory / "updates.jsonl").read_text(
        encoding="utf-8"
    ).strip()
    assert json.loads(updates)["payload"]["actions"][0]["action"] == "PICK"
    final = json.loads(
        (directory / "final.json").read_text(encoding="utf-8")
    )
    assert final["status"] == "COMPLETED"
    assert final["result"]["score"] == 100
