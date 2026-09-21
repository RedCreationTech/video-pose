import json
from pathlib import Path

from video_pose.session_audit import (
    SessionAuditMetadata,
    SessionAuditWriter,
)


def test_session_audit_persists_runtime_fingerprint(
    tmp_path: Path,
) -> None:
    writer = SessionAuditWriter(tmp_path)
    metadata = SessionAuditMetadata(
        session_id="fingerprinted",
        operation="assembly",
        workstation_id="ws-1",
        rule_set_version=2,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
        capture_backend="gstreamer-native",
        timestamp_source="reference",
        sync_tolerance_ms=20.0,
        camera_clock_offsets_ms={
            "front": 0.0,
            "left": 3.5,
        },
        config_sha256="a" * 64,
        rules_sha256="b" * 64,
    )
    directory = writer.start(metadata)
    payload = json.loads(
        (directory / "metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["capture_backend"] == "gstreamer-native"
    assert payload["timestamp_source"] == "reference"
    assert payload["camera_clock_offsets_ms"]["left"] == 3.5
    assert payload["config_sha256"] == "a" * 64
    assert payload["rules_sha256"] == "b" * 64
