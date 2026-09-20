from video_pose.live_health import LiveHealthRegistry
from video_pose.resource_usage import ResourceSnapshot


def test_health_registry_reports_latency_percentiles_and_resources() -> None:
    health = LiveHealthRegistry([])
    for latency in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        health.frame_set_processed(float(latency))
    health.record_resources(
        ResourceSnapshot(
            rss_mb=256.0,
            gpu_allocated_mb=100.0,
            gpu_reserved_mb=200.0,
        )
    )

    runtime = health.snapshot().runtime
    assert runtime.processing_latency_p95_ms >= 90.0
    assert runtime.processing_latency_p99_ms == 100.0
    assert runtime.current_rss_mb == 256.0
    assert runtime.gpu_reserved_mb == 200.0
