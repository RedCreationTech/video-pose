from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry([])

    def set_event_callback(self, _callback) -> None:
        pass

    def health_snapshot(self):
        return self.health.snapshot()

    def session_timeline(self, session_id):
        return {
            "session_id": session_id,
            "events": [
                {
                    "event_id": "start",
                    "timestamp": "2026-09-21T00:00:00+00:00",
                    "type": "SESSION_STARTED",
                    "severity": None,
                    "title": "Session started",
                    "detail": "",
                    "data": {},
                }
            ],
        }


def test_session_timeline_api() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    response = client.get(
        "/api/v1/sessions/s1/timeline"
    )
    assert response.status_code == 200
    assert response.json()["events"][0]["type"] == (
        "SESSION_STARTED"
    )
