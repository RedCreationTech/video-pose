from video_pose.gstreamer_capture import OpenCVGStreamerLiveCamera
from video_pose.live_capture_factory import build_live_camera_factory
from video_pose.live_gateway import OpenCVLiveCamera
from video_pose.runtime_config import LiveCaptureRuntimeConfig
from video_pose.video_manifest import ReplayManifest


def _manifest() -> ReplayManifest:
    return ReplayManifest.model_validate(
        {
            "session_id": "s1",
            "workstation_id": "ws1",
            "cameras": [
                {"camera_id": "f", "position": "FRONT", "uri": "rtsp://f"},
                {"camera_id": "r", "position": "REAR", "uri": "rtsp://r"},
                {"camera_id": "l", "position": "LEFT", "uri": "rtsp://l"},
                {"camera_id": "x", "position": "RIGHT", "uri": "rtsp://x"},
            ],
        }
    )


def test_opencv_factory_uses_default_camera() -> None:
    factory = build_live_camera_factory(
        _manifest(),
        LiveCaptureRuntimeConfig(backend="opencv"),
    )
    camera = factory("f", "rtsp://f")
    assert type(camera) is OpenCVLiveCamera


def test_gstreamer_factory_uses_manifest_codec() -> None:
    manifest = _manifest()
    manifest.cameras[0].codec = "h265"
    factory = build_live_camera_factory(
        manifest,
        LiveCaptureRuntimeConfig(backend="gstreamer-opencv"),
    )
    camera = factory("f", "rtsp://f")
    assert isinstance(camera, OpenCVGStreamerLiveCamera)
    assert camera.codec == "h265"
