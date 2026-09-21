from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    StorageHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_storage_metrics_without_paths() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(),
        storage=[
            StorageHealthSnapshot(
                name="evidence",
                configured_path="/secret/site/evidence",
                probe_path="/secret/site",
                total_bytes=1000,
                used_bytes=750,
                free_bytes=250,
                free_ratio=0.25,
            )
        ],
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert (
        'video_pose_storage_free_bytes{name="evidence"} 250'
        in rendered
    )
    assert (
        'video_pose_storage_free_ratio{name="evidence"} 0.25'
        in rendered
    )
    assert "/secret/site" not in rendered
