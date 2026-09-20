from pathlib import Path

from video_pose.camera_model import (
    build_perspective_profile,
    load_camera_model_profile,
    load_control_points,
    validate_calibration_health,
)

ROOT = Path(__file__).resolve().parents[1]


def test_camera_model_builds_expected_projection() -> None:
    source = load_camera_model_profile(
        ROOT / "fixtures/calibration/camera-model-demo.yaml"
    )
    profile = build_perspective_profile(source)
    front = profile.camera("cam-front")
    left = profile.camera("cam-left")
    assert front is not None
    assert left is not None
    assert front.projection == [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]
    assert left.projection[0][3] == -1.0


def test_calibration_health_passes_exact_control_points() -> None:
    source = load_camera_model_profile(
        ROOT / "fixtures/calibration/camera-model-demo.yaml"
    )
    profile = build_perspective_profile(source)
    controls = load_control_points(
        ROOT / "fixtures/calibration/control-points-demo.yaml"
    )
    report = validate_calibration_health(
        profile,
        controls,
        max_rmse=0.001,
    )
    assert report.passed is True
    assert all(camera.rmse < 1e-9 for camera in report.cameras)
