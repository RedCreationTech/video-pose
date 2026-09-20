from pathlib import Path

from video_pose.observations import Observation
from video_pose.perspective import load_perspective_calibration
from video_pose.triangulation import TriangulationProcessor

ROOT = Path(__file__).resolve().parents[1]


def test_triangulation_processor_updates_world_keypoints() -> None:
    profile = load_perspective_calibration(
        ROOT / "fixtures/calibration/perspective-demo.yaml"
    )
    processor = TriangulationProcessor(profile, max_reprojection_rmse=0.1)
    observations = [
        Observation.model_validate(
            {
                "observation_id": "front-wrist",
                "session_id": "s1",
                "camera_id": "cam-front",
                "timestamp_ms": 0,
                "type": "BODY_KEYPOINT",
                "entity_id": "world-person-0001:right_wrist",
                "entity_class": "right_wrist",
                "confidence": 0.9,
                "point_2d": {"x": 0.5, "y": 0.25},
            }
        ),
        Observation.model_validate(
            {
                "observation_id": "left-wrist",
                "session_id": "s1",
                "camera_id": "cam-left",
                "timestamp_ms": 0,
                "type": "BODY_KEYPOINT",
                "entity_id": "world-person-0001:right_wrist",
                "entity_class": "right_wrist",
                "confidence": 0.9,
                "point_2d": {"x": 0.25, "y": 0.25},
            }
        ),
    ]
    output = processor.process(observations)
    assert all(item.point_3d is not None for item in output)
    point = output[0].point_3d
    assert point is not None
    assert abs(point.x - 2.0) < 1e-6
    assert abs(point.y - 1.0) < 1e-6
    assert abs(point.z - 4.0) < 1e-6
    assert output[0].attributes["triangulated_views"] == 2
