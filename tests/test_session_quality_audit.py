from video_pose.live_health import (
    AuditHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.runtime_config import SessionQualityRuntimeConfig
from video_pose.session_quality import SessionQualityMonitor


def test_audit_quality_uses_session_local_error_delta() -> None:
    monitor = SessionQualityMonitor(
        SessionQualityRuntimeConfig(
            enabled=True,
            monitor_cameras=False,
            monitor_sync=False,
            monitor_audit=True,
            audit_grace_ms=0,
            max_audit_error_delta=0,
        ),
        camera_ids=[],
    )
    baseline = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        audit=AuditHealthSnapshot(
            status="READY",
            write_errors_total=7,
        ),
        ready=True,
    )
    assert monitor.observe(
        baseline,
        now_monotonic_ms=0,
    ) == []

    failed = baseline.model_copy(
        update={
            "audit": AuditHealthSnapshot(
                status="DEGRADED",
                write_errors_total=8,
                last_error="disk full",
            )
        }
    )
    incident = monitor.observe(
        failed,
        now_monotonic_ms=100,
    )
    assert len(incident) == 1
    assert incident[0].rule_id == "SYSTEM-QUALITY-AUDIT"
    assert incident[0].actual["write_errors_delta"] == 1
