from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    StorageHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def test_soak_fails_storage_headroom_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            min_storage_free_ratio=0.10,
            min_storage_free_gb=5.0,
        )
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            storage=[
                StorageHealthSnapshot(
                    name="audit",
                    configured_path="/audit",
                    probe_path="/",
                    total_bytes=100 * 1024**3,
                    used_bytes=96 * 1024**3,
                    free_bytes=4 * 1024**3,
                    free_ratio=0.04,
                )
            ],
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.min_storage_free_ratio == 0.04
    assert report.min_storage_free_bytes == 4 * 1024**3
    assert any(
        "min_storage_free_ratio" in item
        for item in report.failures
    )
    assert any(
        "min_storage_free_gb" in item
        for item in report.failures
    )
