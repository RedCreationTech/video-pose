from video_pose.live_health import CameraState, LiveHealthRegistry
from video_pose.live_metrics import render_prometheus


def test_health_registry_tracks_camera_and_runtime_metrics() -> None:
    health = LiveHealthRegistry(["front"], queue_capacity=2)
    health.camera_frame("front", monotonic_ms=1000)
    health.camera_frame("front", monotonic_ms=1040)
    health.camera_error("front", RuntimeError("decode failed"))
    health.camera_reconnecting("front")
    health.frame_set_received()
    health.frame_set_dropped()
    health.frame_set_processed(42.5)
    health.set_queue_depth(1)

    snapshot = health.snapshot()
    camera = snapshot.cameras[0]
    assert camera.state == CameraState.RECONNECTING
    assert camera.frames_total == 2
    assert camera.read_errors_total == 1
    assert camera.reconnect_total == 1
    assert snapshot.runtime.frame_sets_dropped_total == 1
    assert snapshot.runtime.queue_depth == 1

    rendered = render_prometheus(snapshot)
    assert "video_pose_camera_frames_total" in rendered
    assert "video_pose_frame_sets_dropped_total 1" in rendered
