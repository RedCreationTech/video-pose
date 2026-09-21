from video_pose.session_audit import SessionAuditMetadata
from video_pose.session_controller import ManagedSessionState


def test_session_state_and_audit_accept_trace_id() -> None:
    trace_id = "a" * 32
    state = ManagedSessionState(
        session_id="s1",
        trace_id=trace_id,
        operation="assembly",
        workstation_id="ws1",
        status="RUNNING",
        started_at="2026-09-21T00:00:00+00:00",
    )
    metadata = SessionAuditMetadata(
        session_id="s1",
        trace_id=trace_id,
        operation="assembly",
        workstation_id="ws1",
        rule_set_version=1,
        started_at="2026-09-21T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="model.pt",
    )
    assert state.trace_id == trace_id
    assert metadata.trace_id == trace_id
