import pytest

from video_pose.live_video import MemoryFrameStore
from video_pose.video_manifest import CameraPosition
from video_pose.video_replay import FrameRef


def test_memory_frame_store_evicts_old_frames() -> None:
    store = MemoryFrameStore(max_frames=4)
    uris = [
        store.put(camera_id="front", sequence=index, image=f"frame-{index}")
        for index in range(5)
    ]
    old_ref = FrameRef(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri=uris[0],
        source_timestamp_ms=0,
        normalized_timestamp_ms=0,
    )
    with pytest.raises(KeyError):
        store.load(old_ref)

    latest_ref = old_ref.__class__(
        camera_id="front",
        position=CameraPosition.FRONT,
        uri=uris[-1],
        source_timestamp_ms=4,
        normalized_timestamp_ms=4,
    )
    assert store.load(latest_ref).image == "frame-4"
