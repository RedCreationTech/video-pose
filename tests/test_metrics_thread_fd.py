from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.live_metrics import render_prometheus


def test_prometheus_renders_thread_and_fd_metrics() -> None:
    snapshot = LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(
            current_thread_count=12,
            max_thread_count=14,
            current_open_fds=30,
            max_open_fds=35,
        ),
        ready=True,
    )
    rendered = render_prometheus(snapshot)
    assert "video_pose_process_threads 12" in rendered
    assert "video_pose_process_threads_max 14" in rendered
    assert "video_pose_process_open_fds 30" in rendered
    assert "video_pose_process_open_fds_max 35" in rendered
