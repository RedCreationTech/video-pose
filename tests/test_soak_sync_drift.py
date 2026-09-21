from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def test_soak_fails_excessive_sync_drift() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_sync_miss_ratio=1.0,
            max_sync_p99_skew_ms=100.0,
            min_sync_emitted_total=1,
            max_abs_sync_drift_ms_per_minute=2.0,
        )
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            sync=SyncHealthSnapshot(
                reference_frames_total=100,
                emitted_total=100,
                camera_drift_ms_per_minute={
                    "front": 0.0,
                    "left": -3.5,
                },
            ),
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.max_abs_sync_drift_ms_per_minute == 3.5
    assert any(
        "max_abs_sync_drift_ms_per_minute" in item
        for item in report.failures
    )
