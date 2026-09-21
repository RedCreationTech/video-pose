from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self):
        self.health = LiveHealthRegistry([])

    def set_event_callback(self, _callback):
        pass

    def health_snapshot(self):
        return self.health.snapshot()

    def runtime_version(self):
        return {
            "application_version": "0.48.0",
            "git_sha": "deadbeef",
            "image_digest": None,
            "release_fingerprint": "f" * 64,
            "runtime_fingerprint": {
                "capture_backend": "opencv",
                "timestamp_source": "arrival",
                "sync_tolerance_ms": 20,
                "camera_clock_offsets_ms": {},
            },
        }


def test_runtime_version_endpoint() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    response = client.get("/api/v1/runtime/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["application_version"] == "0.48.0"
    assert payload["release_fingerprint"] == "f" * 64
