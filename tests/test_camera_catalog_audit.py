from video_pose.live_health import LiveHealthRegistry
from video_pose.live_video import MemoryFrameStore
from video_pose.persistent_camera import PersistentCameraHub
from video_pose.video_manifest import ReplayManifest


class FakeGateway:
    def start(self, _callback):
        pass

    def stop(self):
        pass


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "catalog-audit",
            "workstation_id": "ws-1",
            "cameras": [
                {
                    "camera_id": "f",
                    "position": "FRONT",
                    "uri": "rtsp://f",
                },
                {
                    "camera_id": "r",
                    "position": "REAR",
                    "uri": "rtsp://r",
                },
                {
                    "camera_id": "l",
                    "position": "LEFT",
                    "uri": "rtsp://l",
                },
                {
                    "camera_id": "x",
                    "position": "RIGHT",
                    "uri": "rtsp://x",
                },
            ],
        }
    )


def test_camera_catalog_exposes_timebase_without_uri() -> None:
    hub = PersistentCameraHub(
        manifest=_manifest(),
        frame_store=MemoryFrameStore(),
        health=LiveHealthRegistry(["f", "r", "l", "x"]),
        gateway=FakeGateway(),  # type: ignore[arg-type]
        capture_backend="gstreamer-native",
        timestamp_source="reference",
    )
    item = hub.camera_catalog()[0]
    assert item["capture_backend"] == "gstreamer-native"
    assert item["timestamp_source"] == "reference"
    assert "uri" not in item
