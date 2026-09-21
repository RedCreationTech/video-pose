from video_pose.live_health import (
    AuditHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_audit_health() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        audit=AuditHealthSnapshot(
            status="DEGRADED",
            write_errors_total=3,
            last_error="disk full",
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert "video_pose_audit_ready 0" in rendered
    assert "video_pose_audit_write_errors_total 3" in rendered
    assert "disk full" not in rendered
