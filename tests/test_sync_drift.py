from video_pose.live_health import LiveHealthRegistry


def test_sync_drift_uses_offset_trend_not_absolute_offset() -> None:
    health = LiveHealthRegistry([])
    health.enable_sync()

    samples = [
        (0.0, 8.0),
        (30_000.0, 9.5),
        (60_000.0, 11.0),
    ]
    for timestamp_ms, offset_ms in samples:
        health.sync_reference_frame()
        health.sync_emitted(
            reference_timestamp_ms=timestamp_ms,
            skew_ms=abs(offset_ms),
            camera_offsets_ms={
                "front": 0.0,
                "left": offset_ms,
            },
        )

    snapshot = health.snapshot()
    assert snapshot.sync is not None
    drift = snapshot.sync.camera_drift_ms_per_minute
    assert abs(drift["front"]) < 1e-9
    assert abs(drift["left"] - 3.0) < 1e-9
    assert snapshot.sync.camera_offsets_ms["left"] == 11.0


def test_sync_drift_waits_for_minimum_time_window() -> None:
    health = LiveHealthRegistry([])
    health.enable_sync()
    health.sync_reference_frame()
    health.sync_emitted(
        reference_timestamp_ms=0,
        skew_ms=0,
        camera_offsets_ms={"left": 0.0},
    )
    health.sync_reference_frame()
    health.sync_emitted(
        reference_timestamp_ms=10_000,
        skew_ms=5,
        camera_offsets_ms={"left": 5.0},
    )

    snapshot = health.snapshot()
    assert snapshot.sync is not None
    assert snapshot.sync.camera_drift_ms_per_minute["left"] == 0.0
