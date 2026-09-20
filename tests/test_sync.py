from video_pose.sync import nearest_timestamp, synchronize_timestamps
from video_pose.video_manifest import CameraPosition


def test_nearest_timestamp() -> None:
    assert nearest_timestamp([0.0, 40.0, 80.0], 43.0) == 40.0


def test_synchronizes_four_camera_timestamps_within_tolerance() -> None:
    streams = {
        CameraPosition.FRONT: [0.0, 40.0, 80.0],
        CameraPosition.REAR: [2.0, 42.0, 82.0],
        CameraPosition.LEFT: [-3.0, 37.0, 77.0],
        CameraPosition.RIGHT: [1.0, 41.0, 81.0],
    }
    frames = synchronize_timestamps(streams, tolerance_ms=10.0)
    assert len(frames) == 3
    assert max(frame.skew_ms for frame in frames) <= 5.0


def test_drops_reference_frame_when_any_view_is_outside_tolerance() -> None:
    streams = {
        CameraPosition.FRONT: [0.0, 40.0],
        CameraPosition.REAR: [2.0, 42.0],
        CameraPosition.LEFT: [100.0],
        CameraPosition.RIGHT: [1.0, 41.0],
    }
    assert synchronize_timestamps(streams, tolerance_ms=10.0) == []
