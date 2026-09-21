from video_pose.live_capture_factory import build_live_camera_factory
from video_pose.native_gstreamer_capture import NativeGStreamerLiveCamera
from video_pose.runtime_config import LiveCaptureRuntimeConfig
from video_pose.video_manifest import ReplayManifest


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "s1",
            "workstation_id": "ws1",
            "cameras": [
                {
                    "camera_id": "front",
                    "position": "FRONT",
                    "uri": "rtsp://front",
                    "codec": "h265",
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


def test_factory_builds_native_gstreamer_camera_lazily() -> None:
    factory = build_live_camera_factory(
        _manifest(),
        LiveCaptureRuntimeConfig(
            backend="gstreamer-native",
            native_timestamp_source="reference",
        ),
    )
    camera = factory("front", "rtsp://front")
    assert isinstance(camera, NativeGStreamerLiveCamera)
    assert camera.codec == "h265"
    assert camera.rfc7273_sync is True
    assert camera.timestamp_source.value == "reference"
