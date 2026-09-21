from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_sync_drift() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        sync=SyncHealthSnapshot(
            camera_drift_ms_per_minute={
                "front": 0.0,
                "left": 2.5,
            }
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert (
        'video_pose_sync_camera_drift_ms_per_minute{camera="left"} 2.5'
        in rendered
    )
