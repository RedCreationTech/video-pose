from video_pose.observations import Observation
from video_pose.tool_operation import ToolOperationRecognizer


def _facts(timestamp: float, x: float) -> list[Observation]:
    common = {
        "session_id": "s1",
        "camera_id": "cam-front",
        "timestamp_ms": timestamp,
        "entity_id": "tool-1",
        "entity_class": "torque_wrench",
        "confidence": 0.95,
    }
    return [
        Observation.model_validate(
            {
                **common,
                "observation_id": f"object-{timestamp}",
                "type": "OBJECT",
                "point_3d": {"x": x, "y": 0, "z": 0},
            }
        ),
        Observation.model_validate(
            {
                **common,
                "observation_id": f"held-{timestamp}",
                "type": "RELATION",
                "relation": "HELD_BY",
                "target_id": "right_wrist",
            }
        ),
        Observation.model_validate(
            {
                **common,
                "observation_id": f"zone-{timestamp}",
                "type": "ZONE_RELATION",
                "relation": "IN",
                "zone": "assembly_zone",
            }
        ),
    ]


def test_tool_operation_emits_after_path_threshold() -> None:
    recognizer = ToolOperationRecognizer(
        "s1",
        tool_classes={"torque_wrench"},
        operation_zones={"assembly_zone"},
        min_path_length=30,
    )
    assert recognizer.ingest(_facts(0, 0)) == []
    assert recognizer.ingest(_facts(40, 15)) == []
    events = recognizer.ingest(_facts(80, 35))
    assert len(events) == 1
    assert events[0].action.value == "OPERATE_TOOL"
    assert events[0].target_zone == "assembly_zone"
