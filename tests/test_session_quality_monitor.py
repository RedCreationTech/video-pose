from video_pose.live_health import (
    CameraHealthSnapshot,
    CameraState,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.runtime_config import SessionQualityRuntimeConfig
from video_pose.session_quality import SessionQualityMonitor


def _snapshot(
    camera_state=CameraState.ONLINE,
    last_frame_ms=1000.0,
    emitted=10,
):
    return LiveHealthSnapshot(
        cameras=[
            CameraHealthSnapshot(
                camera_id="front",
                state=camera_state,
                last_frame_monotonic_ms=last_frame_ms,
            )
        ],
        runtime=RuntimeHealthSnapshot(),
        sync=SyncHealthSnapshot(
            reference_frames_total=10,
            emitted_total=emitted,
            miss_total=0,
            skew_p99_ms=5.0,
            camera_drift_ms_per_minute={"front": 0.0},
        ),
        ready=True,
    )


def test_camera_failure_requires_grace_and_rearms_after_recovery() -> None:
    config = SessionQualityRuntimeConfig(
        enabled=True,
        monitor_sync=False,
        camera_grace_ms=1000,
        max_camera_staleness_ms=500,
    )
    monitor = SessionQualityMonitor(
        config,
        camera_ids=["front"],
    )

    assert monitor.observe(
        _snapshot(CameraState.RECONNECTING, 0),
        now_monotonic_ms=1000,
    ) == []
    first = monitor.observe(
        _snapshot(CameraState.RECONNECTING, 0),
        now_monotonic_ms=2100,
    )
    assert len(first) == 1
    assert first[0].type == "SYSTEM_QUALITY"

    assert monitor.observe(
        _snapshot(CameraState.ONLINE, 3000),
        now_monotonic_ms=3000,
    ) == []

    assert monitor.observe(
        _snapshot(CameraState.RECONNECTING, 3000),
        now_monotonic_ms=4000,
    ) == []
    second = monitor.observe(
        _snapshot(CameraState.RECONNECTING, 3000),
        now_monotonic_ms=5100,
    )
    assert len(second) == 1
    assert second[0].event_id != first[0].event_id


def test_sync_stall_becomes_quality_violation() -> None:
    config = SessionQualityRuntimeConfig(
        enabled=True,
        monitor_cameras=False,
        sync_grace_ms=1000,
    )
    monitor = SessionQualityMonitor(
        config,
        camera_ids=[],
    )
    assert monitor.observe(
        _snapshot(emitted=10),
        now_monotonic_ms=1000,
    ) == []
    incident = monitor.observe(
        _snapshot(emitted=10),
        now_monotonic_ms=2100,
    )
    assert len(incident) == 1
    assert incident[0].rule_id == "SYSTEM-QUALITY-SYNC"
