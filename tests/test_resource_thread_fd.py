from video_pose.resource_usage import sample_process_resources


def test_resource_sampler_reports_thread_and_fd_state() -> None:
    snapshot = sample_process_resources()
    assert snapshot.rss_mb > 0
    assert snapshot.thread_count >= 1
    if snapshot.open_fds is not None:
        assert snapshot.open_fds >= 0
