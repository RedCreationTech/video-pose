from video_pose.live_health import (
    LiveHealthSnapshot,
    ModelWarmupHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_model_warmup_metrics() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        model_warmup=ModelWarmupHealthSnapshot(
            enabled=True,
            status="PASS",
            latency_ms=123.5,
            detector_result_count=0,
            pose_result_count=1,
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert "video_pose_model_warmup_ready 1" in rendered
    assert "video_pose_model_warmup_latency_ms 123.5" in rendered
    assert "video_pose_model_warmup_pose_results 1" in rendered
