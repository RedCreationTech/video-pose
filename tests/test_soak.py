from video_pose.live_health import (
    CameraHealthSnapshot,
    CameraState,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.soak import SoakMonitor, SoakThresholds


def _snapshot(
    *,
    ready: bool,
    received: int,
    processed: int,
    dropped: int,
    processing_errors: int = 0,
    reconnects: int = 0,
    read_errors: int = 0,
    max_latency: float = 100.0,
) -> LiveHealthSnapshot:
    return LiveHealthSnapshot(
        cameras=[
            CameraHealthSnapshot(
                camera_id="front",
                state=CameraState.ONLINE,
                frames_total=100,
                read_errors_total=read_errors,
                reconnect_total=reconnects,
            )
        ],
        runtime=RuntimeHealthSnapshot(
            frame_sets_received_total=received,
            frame_sets_processed_total=processed,
            frame_sets_dropped_total=dropped,
            processing_errors_total=processing_errors,
            queue_capacity=2,
            max_processing_latency_ms=max_latency,
        ),
        ready=ready,
    )


def test_soak_report_passes_healthy_samples() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=0.9,
            max_drop_ratio=0.1,
            max_processing_latency_ms=500,
        )
    )
    monitor.add(
        0,
        _snapshot(
            ready=True,
            received=10,
            processed=10,
            dropped=0,
        ),
    )
    monitor.add(
        60,
        _snapshot(
            ready=True,
            received=100,
            processed=98,
            dropped=2,
        ),
    )
    report = monitor.report()
    assert report.passed is True
    assert report.ready_ratio == 1.0
    assert report.drop_ratio == 0.02


def test_soak_report_explains_failed_gate() -> None:
    monitor = SoakMonitor(
        SoakThresholds(
            min_ready_ratio=1.0,
            max_drop_ratio=0.01,
            max_processing_errors=0,
            max_camera_reconnects=0,
            max_processing_latency_ms=200,
        )
    )
    monitor.add(
        0,
        _snapshot(
            ready=False,
            received=100,
            processed=80,
            dropped=20,
            processing_errors=1,
            reconnects=2,
            max_latency=900,
        ),
    )
    report = monitor.report()
    assert report.passed is False
    assert any("ready_ratio" in item for item in report.failures)
    assert any("drop_ratio" in item for item in report.failures)
    assert any("processing_errors_total" in item for item in report.failures)
    assert any("camera_reconnect_total" in item for item in report.failures)
    assert any("max_processing_latency_ms" in item for item in report.failures)
