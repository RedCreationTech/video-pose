from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_sync_metrics_and_offsets() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        sync=SyncHealthSnapshot(
            reference_frames_total=100,
            emitted_total=95,
            miss_total=5,
            tolerance_miss_total=5,
            success_ratio=0.95,
            last_skew_ms=7.0,
            max_skew_ms=12.0,
            skew_p95_ms=9.0,
            skew_p99_ms=11.0,
            camera_offsets_ms={
                "front": 0.0,
                "left": -3.0,
            },
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert "video_pose_sync_emitted_total 95" in rendered
    assert "video_pose_sync_success_ratio 0.95" in rendered
    assert "video_pose_sync_skew_p99_ms 11.0" in rendered
    assert (
        'video_pose_sync_camera_offset_ms{camera="left"} -3.0'
        in rendered
    )
