from video_pose.live_health import (
    LiveHealthSnapshot,
    ModelWarmupHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def test_soak_fails_model_warmup_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_model_warmup_latency_ms=1000,
        )
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            model_warmup=ModelWarmupHealthSnapshot(
                enabled=True,
                status="FAIL",
                latency_ms=1200,
                error_type="RuntimeError",
            ),
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert report.model_warmup_status == "FAIL"
    assert report.model_warmup_latency_ms == 1200
    assert any(
        "model_warmup_status" in item
        for item in report.failures
    )
