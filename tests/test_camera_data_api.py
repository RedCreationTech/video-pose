from types import SimpleNamespace

from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry([])
        self.callback = None

    def set_event_callback(self, callback) -> None:
        self.callback = callback

    def health_snapshot(self):
        return self.health.snapshot()

    def camera_catalog(self):
        return [
            {
                "camera_id": "front",
                "position": "FRONT",
                "state": "ONLINE",
                "snapshot_available": True,
            }
        ]

    def camera_snapshot(self, camera_id: str, *, quality: int):
        assert camera_id == "front"
        assert quality == 75
        return SimpleNamespace(
            content=b"jpeg-bytes",
            media_type="image/jpeg",
            timestamp_ms=1234.5,
        )

    def current(self):
        return None

    def current_evaluation(self):
        return {
            "score": 98.0,
            "passed": True,
            "steps": [],
            "violations": [],
        }

    def list_sessions(self, _limit=100):
        return []

    def get_session(self, _session_id):
        return None

    def persistence_health(self):
        return {"configured": False, "status": "DISABLED"}


def test_camera_catalog_snapshot_and_current_evaluation_endpoints() -> None:
    controller = FakeController()
    app = create_managed_live_app(
        controller,
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)

    cameras = client.get("/api/v1/cameras")
    assert cameras.status_code == 200
    assert cameras.json()[0]["camera_id"] == "front"

    snapshot = client.get(
        "/api/v1/cameras/front/snapshot.jpg?quality=75"
    )
    assert snapshot.status_code == 200
    assert snapshot.content == b"jpeg-bytes"
    assert snapshot.headers["cache-control"] == "no-store"
    assert snapshot.headers["x-video-pose-timestamp-ms"] == "1234.5"

    evaluation = client.get(
        "/api/v1/sessions/current/evaluation"
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["score"] == 98.0
