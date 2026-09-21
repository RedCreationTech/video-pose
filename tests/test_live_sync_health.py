from video_pose.live_health import LiveHealthRegistry
from video_pose.live_video import LiveFrameSynchronizer, MemoryFrameStore
from video_pose.video_manifest import ReplayManifest


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "sync-health",
            "workstation_id": "ws-1",
            "sync_tolerance_ms": 10,
            "cameras": [
                {
                    "camera_id": "front",
                    "position": "FRONT",
                    "uri": "rtsp://front",
                },
                {
                    "camera_id": "rear",
                    "position": "REAR",
                    "uri": "rtsp://rear",
                },
                {
                    "camera_id": "left",
                    "position": "LEFT",
                    "uri": "rtsp://left",
                },
                {
                    "camera_id": "right",
                    "position": "RIGHT",
                    "uri": "rtsp://right",
                },
            ],
        }
    )


def test_live_sync_health_tracks_success_and_tolerance_miss() -> None:
    health = LiveHealthRegistry(
        ["front", "rear", "left", "right"]
    )
    sync = LiveFrameSynchronizer(
        _manifest(),
        MemoryFrameStore(),
        health=health,
    )

    for camera_id in ["rear", "left", "right"]:
        sync.push(
            camera_id=camera_id,
            source_timestamp_ms=100,
            image=camera_id,
        )
    frame_set = sync.push(
        camera_id="front",
        source_timestamp_ms=100,
        image="front",
    )
    assert frame_set is not None

    sync.push(
        camera_id="rear",
        source_timestamp_ms=200,
        image="rear-2",
    )
    sync.push(
        camera_id="right",
        source_timestamp_ms=200,
        image="right-2",
    )
    missed = sync.push(
        camera_id="front",
        source_timestamp_ms=200,
        image="front-2",
    )
    assert missed is None

    snapshot = health.snapshot()
    assert snapshot.sync is not None
    assert snapshot.sync.reference_frames_total == 2
    assert snapshot.sync.emitted_total == 1
    assert snapshot.sync.miss_total == 1
    assert snapshot.sync.tolerance_miss_total == 1
    assert snapshot.sync.success_ratio == 0.5
    assert snapshot.sync.skew_p99_ms == 0.0
