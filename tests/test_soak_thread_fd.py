from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def _snapshot(threads: int, fds: int) -> LiveHealthSnapshot:
    return LiveHealthSnapshot(
        cameras=[],
        runtime=RuntimeHealthSnapshot(
            current_thread_count=threads,
            current_open_fds=fds,
        ),
        ready=True,
    )


def test_soak_fails_thread_and_fd_growth_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_thread_growth=2,
            max_open_fd_growth=3,
        )
    )
    monitor.add(0, _snapshot(10, 20))
    monitor.add(60, _snapshot(14, 26))
    report = monitor.report()

    assert report.thread_growth == 4
    assert report.open_fd_growth == 6
    assert report.passed is False
    assert any(
        "thread_growth" in item
        for item in report.failures
    )
    assert any(
        "open_fd_growth" in item
        for item in report.failures
    )


def test_soak_handles_platform_without_open_fd_metric() -> None:
    monitor = SoakMonitor(
        SoakThresholds(min_ready_ratio=1.0)
    )
    monitor.add(
        0,
        LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(
                current_thread_count=5,
                current_open_fds=None,
            ),
            ready=True,
        ),
    )
    report = monitor.report()
    assert report.open_fd_growth is None
