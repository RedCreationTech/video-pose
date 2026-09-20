from video_pose.observations import Observation, Point2D
from video_pose.relations import HumanObjectRelationBuilder, point_to_box_distance


def _object(timestamp: float, x1: float = 100, x2: float = 160) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": f"object-{timestamp}",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": timestamp,
            "type": "OBJECT",
            "entity_id": "tool-1",
            "entity_class": "torque_wrench",
            "confidence": 0.95,
            "bbox": {"x1": x1, "y1": 100, "x2": x2, "y2": 160},
        }
    )


def _wrist(timestamp: float, x: float, y: float) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": f"wrist-{timestamp}",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": timestamp,
            "type": "BODY_KEYPOINT",
            "entity_id": "person-1:right_wrist",
            "entity_class": "right_wrist",
            "confidence": 0.93,
            "point_2d": {"x": x, "y": y},
            "attributes": {"person_id": "person-1"},
        }
    )


def test_point_to_box_distance_is_zero_inside_box() -> None:
    obj = _object(0)
    assert obj.bbox is not None
    assert point_to_box_distance(Point2D(x=120, y=120), obj.bbox) == 0.0


def test_relation_builder_debounces_held_and_free() -> None:
    builder = HumanObjectRelationBuilder(hold_frames=2, free_frames=1)

    initial = builder.enrich([_object(0), _wrist(0, 400, 400)])
    assert [item.relation.value for item in initial] == ["FREE"]

    first_contact = builder.enrich([_object(40), _wrist(40, 130, 130)])
    assert [item.relation.value for item in first_contact] == ["NEAR"]

    held = builder.enrich([_object(80), _wrist(80, 130, 130)])
    assert [item.relation.value for item in held] == ["HELD_BY"]

    released = builder.enrich([_object(120), _wrist(120, 400, 400)])
    assert [item.relation.value for item in released] == ["FREE"]
