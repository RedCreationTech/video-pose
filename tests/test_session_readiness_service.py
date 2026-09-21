from fastapi.testclient import TestClient

from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import (
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
)
from video_pose.live_service import create_managed_live_app
from video_pose.session_controller import SessionStartRequest
from video_pose.session_readiness import (
    SessionNotReadyError,
    SessionReadinessCheck,
    SessionReadinessReport,
)
from video_pose.session_controller import SessionStartRequest


class FakeController:
    def __init__(self):
        self.callback = None

    def set_event_callback(self, callback):
        self.callback = callback

    def health_snapshot(self):
        return LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            ready=True,
        )

    def readiness(self):
        return SessionReadinessReport(
            policy_enabled=True,
            ready=False,
            checks=[
                SessionReadinessCheck(
                    name="sync-warmup",
                    passed=False,
                    detail="emitted=0, required=30",
                )
            ],
        )

    def start(self, _request: SessionStartRequest):
        raise SessionNotReadyError(self.readiness())


def test_managed_service_exposes_session_readiness_and_503() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)

    readiness = client.get("/api/v1/sessions/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False

    health = client.get("/health/ready")
    assert health.status_code == 503
    assert health.json()["session_readiness"]["ready"] is False

    start = client.post("/api/v1/sessions", json={})
    assert start.status_code == 503
    assert start.json()["detail"]["ready"] is False
