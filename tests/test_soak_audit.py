from video_pose.live_health import (
    AuditHealthSnapshot,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def test_soak_fails_audit_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_audit_write_errors=0,
            fail_on_audit_degraded=True,
        )
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            audit=AuditHealthSnapshot(
                status="DEGRADED",
                write_errors_total=1,
            ),
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.audit_write_errors_total == 1
    assert report.audit_degraded is True
    assert any(
        "audit_write_errors_total" in item
        for item in report.failures
    )
