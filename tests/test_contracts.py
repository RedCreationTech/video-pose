import pytest
from pydantic import ValidationError

from video_pose.contracts import ActionEvent


def test_event_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        ActionEvent.model_validate(
            {
                "event_id": "e1",
                "session_id": "s1",
                "sequence": 1,
                "action": "PICK",
                "started_at_ms": 1,
                "confidence": 1.1,
            }
        )


def test_event_rejects_reverse_time() -> None:
    with pytest.raises(ValidationError):
        ActionEvent.model_validate(
            {
                "event_id": "e1",
                "session_id": "s1",
                "sequence": 1,
                "action": "PICK",
                "started_at_ms": 10,
                "ended_at_ms": 9,
                "confidence": 0.9,
            }
        )
