from video_pose.live_video import LiveFrameSynchronizer, MemoryFrameStore
from video_pose.video_manifest import CameraPosition, ReplayManifest


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "live-demo",
            "workstation_id": "ws-1",
            "sync_tolerance_ms": 10,
            "cameras": [
                {
                    "camera_id": "front",
                    "position": "FRONT",
                    "uri": "rtsp://front",
                    "clock_offset_ms": 0,
                },
                {
                    "camera_id": "rear",
                    "position": "REAR",
                    "uri": "rtsp://rear",
                    "clock_offset_ms": -2,
                },
                {
                    "camera_id": "left",
                    "position": "LEFT",
                    "uri": "rtsp://left",
                    "clock_offset_ms": 3,
                },
                {
                    "camera_id": "right",
                    "position": "RIGHT",
                    "uri": "rtsp://right",
                    "clock_offset_ms": 1,
                },
            ],
        }
    )


def test_live_synchronizer_reuses_synchronized_frame_contract() -> None:
    store = MemoryFrameStore()
    sync = LiveFrameSynchronizer(_manifest(), store)

    assert sync.push(
        camera_id="rear",
        source_timestamp_ms=102,
        image="rear-pixels",
    ) is None
    assert sync.push(
        camera_id="left",
        source_timestamp_ms=97,
        image="left-pixels",
    ) is None
    assert sync.push(
        camera_id="right",
        source_timestamp_ms=99,
        image="right-pixels",
    ) is None
    frame_set = sync.push(
        camera_id="front",
        source_timestamp_ms=100,
        image="front-pixels",
    )

    assert frame_set is not None
    assert frame_set.skew_ms == 0
    assert set(frame_set.frames) == set(CameraPosition)
    decoded = store.load(frame_set.frames[CameraPosition.LEFT])
    assert decoded.image == "left-pixels"


def test_live_synchronizer_waits_when_view_is_outside_tolerance() -> None:
    store = MemoryFrameStore()
    sync = LiveFrameSynchronizer(_manifest(), store)

    sync.push(camera_id="rear", source_timestamp_ms=102, image="rear")
    sync.push(camera_id="left", source_timestamp_ms=50, image="left")
    sync.push(camera_id="right", source_timestamp_ms=99, image="right")
    frame_set = sync.push(
        camera_id="front",
        source_timestamp_ms=100,
        image="front",
    )
    assert frame_set is None
