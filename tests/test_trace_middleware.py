from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_live_app


class FakeRuntime:
    def __init__(self):
        self.health = LiveHealthRegistry([])

    def health_snapshot(self):
        return self.health.snapshot()

    def start(self, _callback):
        pass

    def stop(self):
        pass


def test_http_traceparent_preserves_upstream_trace_id() -> None:
    app = create_live_app(
        FakeRuntime(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    incoming = (
        "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-"
        "bbbbbbbbbbbbbbbb-01"
    )
    response = client.get(
        "/health/live",
        headers={"traceparent": incoming},
    )
    assert response.status_code == 200
    outgoing = response.headers["traceparent"]
    assert outgoing.startswith(
        "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-"
    )
    assert "bbbbbbbbbbbbbbbb" not in outgoing
    assert response.headers["x-request-id"] == (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
