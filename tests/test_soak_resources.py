from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def _snapshot(rss: float, p99: float) -> LiveHealthSnapshot:
    return LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(
            frame_sets_received_total=100,
            frame_sets_processed_total=100,
            processing_latency_p99_ms=p99,
            current_rss_mb=rss,
            max_rss_mb=rss,
        ),
        ready=True,
    )


def test_soak_fails_on_rss_growth_and_p99() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_rss_growth_mb=100,
            max_processing_p99_ms=200,
        )
    )
    monitor.add(0, _snapshot(200, 100))
    monitor.add(60, _snapshot(350, 250))
    report = monitor.report()
    assert report.passed is False
    assert report.rss_growth_mb == 150
    assert any("rss_growth_mb" in item for item in report.failures)
    assert any("max_processing_p99_ms" in item for item in report.failures)
