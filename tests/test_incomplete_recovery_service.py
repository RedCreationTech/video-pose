from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self):
        self.callback = None
        self.health = LiveHealthRegistry([])

    def set_event_callback(self, callback):
        self.callback = callback

    def health_snapshot(self):
        return self.health.snapshot()

    def list_incomplete_persistence_sessions(self):
        return [
            {
                "session_id": "stale-1",
                "operation": "assembly",
                "workstation_id": "ws-1",
                "started_at": "2026-09-21T00:00:00+00:00",
                "update_count": 12,
                "last_recorded_at": None,
            }
        ]

    def recover_incomplete_persistence_session(
        self,
        session_id,
        request,
        *,
        recovered_by,
    ):
        return {
            "recovery": {
                "session_id": session_id,
                "reason": request.reason,
                "recovered_by": recovered_by,
            },
            "reconciliation": None,
        }


def test_incomplete_recovery_api_in_dev_admin_mode() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)

    listing = client.get(
        "/api/v1/runtime/persistence/incomplete-sessions"
    )
    assert listing.status_code == 200
    assert listing.json()[0]["session_id"] == "stale-1"

    recovered = client.post(
        "/api/v1/runtime/persistence/incomplete-sessions/"
        "stale-1/recover",
        json={"reason": "operator confirmed host crash"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovery"]["session_id"] == "stale-1"
    assert (
        recovered.json()["recovery"]["recovered_by"]
        == "development"
    )
