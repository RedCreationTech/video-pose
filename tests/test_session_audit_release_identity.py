from video_pose.session_audit import SessionAuditMetadata


def test_session_audit_accepts_release_identity_fields() -> None:
    metadata = SessionAuditMetadata(
        session_id="s1",
        operation="assembly",
        workstation_id="ws1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="model.pt",
        application_version="0.48.0",
        git_sha="a" * 40,
        image_digest="sha256:" + "b" * 64,
        release_fingerprint="c" * 64,
    )
    assert metadata.application_version == "0.48.0"
    assert metadata.release_fingerprint == "c" * 64
