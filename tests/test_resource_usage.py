from video_pose.resource_usage import sample_process_resources


def test_process_resource_sampler_reports_positive_rss() -> None:
    snapshot = sample_process_resources()
    assert snapshot.rss_mb > 0
