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

    def preflight(self):
        return {
            "generated_at": "2026-09-21T00:00:00+00:00",
            "workstation_id": "ws-1",
            "ready": True,
            "failed_checks": [],
            "checks": [],
            "cameras": [],
            "release": {
                "application_version": "0.58.0",
                "git_sha": "abc",
                "image_digest": None,
                "release_fingerprint": "f" * 64,
                "model_release_id": "m1",
            },
            "storage": [],
            "persistence": {
                "configured": False,
                "connectivity": "DISABLED",
            },
        }


def test_runtime_preflight_api() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    response = client.get("/api/v1/runtime/preflight")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["workstation_id"] == "ws-1"
