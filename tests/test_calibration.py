from pathlib import Path

from video_pose.calibration import load_planar_calibration
from video_pose.observations import Point2D

ROOT = Path(__file__).resolve().parents[1]


def test_planar_homography_maps_image_to_world() -> None:
    profile = load_planar_calibration(
        ROOT / "fixtures/calibration/planar-demo.yaml"
    )
    camera = profile.camera("cam-front")
    assert camera is not None
    point = camera.image_to_world(Point2D(x=100, y=50))
    assert point.x == 200
    assert point.y == 100
    assert point.z == 0
