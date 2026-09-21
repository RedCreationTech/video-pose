from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def test_soak_fails_sync_quality_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_sync_miss_ratio=0.10,
            max_sync_p99_skew_ms=10.0,
            min_sync_emitted_total=1,
        )
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            sync=SyncHealthSnapshot(
                reference_frames_total=100,
                emitted_total=70,
                miss_total=30,
                skew_p99_ms=15.0,
            ),
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.sync_miss_ratio == 0.30
    assert report.sync_p99_skew_ms == 15.0
    assert report.sync_emitted_total == 70
    assert any("sync_miss_ratio" in item for item in report.failures)
    assert any("sync_p99_skew_ms" in item for item in report.failures)


def test_soak_skips_sync_gate_when_sync_is_not_enabled() -> None:
    monitor = SoakMonitor(
        SoakThresholds(min_ready_ratio=1.0)
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            sync=None,
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is True
    assert report.sync_miss_ratio is None
