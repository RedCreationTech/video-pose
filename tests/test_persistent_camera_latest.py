from video_pose.live_health import LiveHealthRegistry
from video_pose.live_video import MemoryFrameStore
from video_pose.persistent_camera import PersistentCameraHub
from video_pose.video_manifest import CameraPosition, ReplayManifest
from video_pose.video_replay import FrameRef, SynchronizedFrameSet


class FakeGateway:
    def start(self, callback):
        self.callback = callback

    def stop(self):
        pass


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "preview",
            "workstation_id": "ws",
            "cameras": [
                {"camera_id": "f", "position": "FRONT", "uri": "rtsp://f"},
                {"camera_id": "r", "position": "REAR", "uri": "rtsp://r"},
                {"camera_id": "l", "position": "LEFT", "uri": "rtsp://l"},
                {"camera_id": "x", "position": "RIGHT", "uri": "rtsp://x"},
            ],
        }
    )


def test_hub_exposes_latest_frame_set_and_catalog() -> None:
    store = MemoryFrameStore()
    health = LiveHealthRegistry(["f", "r", "l", "x"])
    gateway = FakeGateway()
    hub = PersistentCameraHub(
        manifest=_manifest(),
        frame_store=store,
        health=health,
        gateway=gateway,  # type: ignore[arg-type]
    )
    hub.start()

    uri = store.put(camera_id="f", sequence=1, image="pixels")
    ref = FrameRef(
        camera_id="f",
        position=CameraPosition.FRONT,
        uri=uri,
        source_timestamp_ms=100,
        normalized_timestamp_ms=100,
    )
    frame_set = SynchronizedFrameSet(
        reference_timestamp_ms=100,
        frames={CameraPosition.FRONT: ref},
        skew_ms=0,
    )
    gateway.callback(frame_set)

    assert hub.latest_frame_set() is frame_set
    catalog = hub.camera_catalog()
    front = next(item for item in catalog if item["camera_id"] == "f")
    rear = next(item for item in catalog if item["camera_id"] == "r")
    assert front["snapshot_available"] is True
    assert rear["snapshot_available"] is False
