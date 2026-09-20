from video_pose.observations import Observation
from video_pose.zone_actions import ZoneTransitionRecognizer


def _zone(timestamp: float) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": f"zone-{timestamp}",
            "session_id": "s1",
            "camera_id": "cam-front",
            "timestamp_ms": timestamp,
            "type": "ZONE_RELATION",
            "entity_id": "person-1",
            "entity_class": "person",
            "confidence": 0.95,
            "relation": "IN",
            "zone": "forbidden_zone",
        }
    )


def test_zone_transition_emits_enter_and_leave() -> None:
    recognizer = ZoneTransitionRecognizer("s1", entity_classes={"person"})
    enter = recognizer.ingest([_zone(100)])
    leave = recognizer.ingest([])
    assert [event.action.value for event in enter] == ["ENTER_ZONE"]
    assert [event.action.value for event in leave] == ["LEAVE_ZONE"]
