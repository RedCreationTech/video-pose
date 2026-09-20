from video_pose.action_composite import CompositeActionRecognizer
from video_pose.contracts import ActionEvent
from video_pose.observations import Observation


class FakeRecognizer:
    def __init__(self, action: str, timestamp: int) -> None:
        self.action = action
        self.timestamp = timestamp

    def ingest(self, _observations: list[Observation]) -> list[ActionEvent]:
        return [
            ActionEvent(
                event_id=f"fake-{self.action}",
                session_id="s1",
                sequence=1,
                action=self.action,
                started_at_ms=self.timestamp,
                confidence=1.0,
            )
        ]


def test_composite_renumbers_events_in_time_order() -> None:
    recognizer = CompositeActionRecognizer(
        [
            FakeRecognizer("PLACE", 200),
            FakeRecognizer("PICK", 100),
        ]
    )
    events = recognizer.ingest([])
    assert [event.action.value for event in events] == ["PICK", "PLACE"]
    assert [event.sequence for event in events] == [1, 2]
