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

    def persistence_health(self):
        return {
            "configured": True,
            "status": "READY",
            "reconciliation": {
                "status": "DIRTY",
            },
        }

    def reconcile_persistence(self):
        return {
            "repaired_count": 1,
            "skipped_count": 2,
            "failed_count": 0,
            "incomplete_count": 0,
            "sessions": [],
        }


def test_admin_can_trigger_persistence_reconcile_in_dev_mode() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/runtime/persistence/reconcile"
    )
    assert response.status_code == 200
    assert response.json()["repaired_count"] == 1
