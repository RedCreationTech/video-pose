import pytest
from pydantic import ValidationError

from video_pose.observations import Observation


def test_held_by_requires_target() -> None:
    with pytest.raises(ValidationError):
        Observation.model_validate(
            {
                "observation_id": "o1",
                "session_id": "s1",
                "camera_id": "front",
                "timestamp_ms": 0,
                "type": "RELATION",
                "entity_id": "part-1",
                "confidence": 0.9,
                "relation": "HELD_BY",
            }
        )


def test_zone_relation_requires_zone() -> None:
    with pytest.raises(ValidationError):
        Observation.model_validate(
            {
                "observation_id": "o1",
                "session_id": "s1",
                "camera_id": "front",
                "timestamp_ms": 0,
                "type": "ZONE_RELATION",
                "entity_id": "part-1",
                "confidence": 0.9,
                "relation": "IN",
            }
        )
