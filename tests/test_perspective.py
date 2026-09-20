from pathlib import Path

from video_pose.observations import Point2D, Point3D
from video_pose.perspective import (
    load_perspective_calibration,
    triangulate_point,
)

ROOT = Path(__file__).resolve().parents[1]


def test_two_view_triangulation_recovers_xyz() -> None:
    profile = load_perspective_calibration(
        ROOT / "fixtures/calibration/perspective-demo.yaml"
    )
    front = profile.camera("cam-front")
    left = profile.camera("cam-left")
    assert front is not None
    assert left is not None

    expected = Point3D(x=2.0, y=1.0, z=4.0)
    front_point = front.project(expected)
    left_point = left.project(expected)
    result = triangulate_point(
        [
            (front, Point2D(x=front_point.x, y=front_point.y)),
            (left, Point2D(x=left_point.x, y=left_point.y)),
        ]
    )
    assert abs(result.point.x - 2.0) < 1e-6
    assert abs(result.point.y - 1.0) < 1e-6
    assert abs(result.point.z - 4.0) < 1e-6
    assert result.reprojection_rmse < 1e-9
