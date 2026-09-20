from pathlib import Path

from video_pose.calibration import load_planar_calibration
from video_pose.observations import Observation
from video_pose.world_projection import WorldProjectionProcessor

ROOT = Path(__file__).resolve().parents[1]


def test_world_projection_adds_point_3d() -> None:
    profile = load_planar_calibration(
        ROOT / "fixtures/calibration/planar-demo.yaml"
    )
    processor = WorldProjectionProcessor(profile)
    observation = Observation.model_validate(
        {
            "observation_id": "obj",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": 0,
            "type": "OBJECT",
            "entity_id": "local-1",
            "entity_class": "component_A",
            "confidence": 0.9,
            "bbox": {"x1": 50, "y1": 20, "x2": 150, "y2": 80},
        }
    )
    output = processor.process([observation])[0]
    assert output.point_3d is not None
    assert output.point_3d.x == 200
    assert output.point_3d.y == 100
