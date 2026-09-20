from video_pose.contracts import ActionType
from video_pose.dwell_action import DwellZoneActionRecognizer
from video_pose.observations import Observation


def _inspection(timestamp: float) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": f"inspect-{timestamp}",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": timestamp,
            "type": "ZONE_RELATION",
            "entity_id": "person-1:nose",
            "entity_class": "nose",
            "confidence": 0.92,
            "relation": "IN",
            "zone": "inspection_zone",
        }
    )


def test_dwell_zone_emits_inspect_after_threshold() -> None:
    recognizer = DwellZoneActionRecognizer(
        "s1",
        action=ActionType.INSPECT,
        zones={"inspection_zone"},
        entity_classes={"nose"},
        dwell_frames=3,
    )
    assert recognizer.ingest([_inspection(0)]) == []
    assert recognizer.ingest([_inspection(40)]) == []
    events = recognizer.ingest([_inspection(80)])
    assert len(events) == 1
    assert events[0].action == ActionType.INSPECT
    assert events[0].target_zone == "inspection_zone"
