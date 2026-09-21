from video_pose.live_health import LiveHealthRegistry
from video_pose.resource_usage import ResourceSnapshot


def test_health_tracks_thread_and_open_fd_high_water_marks() -> None:
    health = LiveHealthRegistry([])
    health.record_resources(
        ResourceSnapshot(
            rss_mb=100,
            thread_count=8,
            open_fds=20,
        )
    )
    health.record_resources(
        ResourceSnapshot(
            rss_mb=110,
            thread_count=11,
            open_fds=27,
        )
    )
    health.record_resources(
        ResourceSnapshot(
            rss_mb=105,
            thread_count=9,
            open_fds=24,
        )
    )
    runtime = health.snapshot().runtime
    assert runtime.current_thread_count == 9
    assert runtime.max_thread_count == 11
    assert runtime.current_open_fds == 24
    assert runtime.max_open_fds == 27
