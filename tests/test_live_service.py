from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_live_app


class FakeRuntime:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry(["front"], queue_capacity=2)

    def health_snapshot(self):
        return self.health.snapshot()

    def start(self, _callback: object) -> None:
        pass

    def stop(self) -> None:
        pass


def test_health_and_metrics_endpoints() -> None:
    runtime = FakeRuntime()
    app = create_live_app(runtime, autostart=False)
    client = TestClient(app)

    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503

    runtime.health.camera_frame("front", monotonic_ms=1000)
    assert client.get("/health/ready").status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "video_pose_ready 1" in metrics.text


def test_latest_endpoint_uses_broker_sequence() -> None:
    runtime = FakeRuntime()
    broker = LiveEventBroker()
    app = create_live_app(
        runtime,
        autostart=False,
        broker=broker,
    )
    client = TestClient(app)

    response = client.get("/api/v1/runtime/latest")
    assert response.json() == {"sequence": 0, "payload": None}
