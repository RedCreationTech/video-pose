from fastapi.testclient import TestClient

from video_pose.auth import (
    AuthConfiguration,
    AuthManager,
    hash_token,
)
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


def _auth() -> AuthManager:
    return AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "operator-1",
                        "role": "OPERATOR",
                        "token_sha256": hash_token("secret"),
                    }
                ],
            }
        )
    )


def test_realtime_ticket_endpoint_requires_bearer() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)

    denied = client.post("/api/v1/auth/realtime-ticket")
    assert denied.status_code == 401

    issued = client.post(
        "/api/v1/auth/realtime-ticket",
        headers={"Authorization": "Bearer secret"},
    )
    assert issued.status_code == 200
    payload = issued.json()
    assert payload["ticket"]
    assert payload["expires_in_seconds"] == 30


def test_realtime_ticket_can_open_websocket_without_bearer_query() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)
    issued = client.post(
        "/api/v1/auth/realtime-ticket",
        headers={"Authorization": "Bearer secret"},
    ).json()

    with client.websocket_connect(
        "/api/v1/realtime?ticket=" + issued["ticket"]
    ) as websocket:
        websocket.close()
