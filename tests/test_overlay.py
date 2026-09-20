from video_pose.observations import Observation
from video_pose.overlay import PrimitiveType, build_overlay_primitives


def test_overlay_builds_box_point_and_relation_text() -> None:
    observations = [
        Observation.model_validate(
            {
                "observation_id": "tool",
                "session_id": "s1",
                "camera_id": "cam-front",
                "timestamp_ms": 0,
                "type": "OBJECT",
                "entity_id": "tool-1",
                "entity_class": "torque_wrench",
                "confidence": 0.95,
                "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 80},
            }
        ),
        Observation.model_validate(
            {
                "observation_id": "wrist",
                "session_id": "s1",
                "camera_id": "cam-front",
                "timestamp_ms": 0,
                "type": "BODY_KEYPOINT",
                "entity_id": "person-1:right_wrist",
                "entity_class": "right_wrist",
                "confidence": 0.9,
                "point_2d": {"x": 50, "y": 40},
            }
        ),
        Observation.model_validate(
            {
                "observation_id": "held",
                "session_id": "s1",
                "camera_id": "cam-front",
                "timestamp_ms": 0,
                "type": "RELATION",
                "entity_id": "tool-1",
                "entity_class": "torque_wrench",
                "confidence": 0.9,
                "relation": "HELD_BY",
                "target_id": "person-1:right_wrist",
            }
        ),
    ]
    primitives = build_overlay_primitives(observations)
    kinds = {primitive.type for primitive in primitives}
    assert kinds == {
        PrimitiveType.BOX,
        PrimitiveType.POINT,
        PrimitiveType.TEXT,
    }
