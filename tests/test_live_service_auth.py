import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from video_pose.auth import AuthConfiguration, AuthManager, hash_token
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_live_app


class FakeRuntime:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry(["front"], queue_capacity=2)
        self.health.camera_frame("front", monotonic_ms=1000)

    def health_snapshot(self):
        return self.health.snapshot()

    def start(self, _callback: object) -> None:
        pass

    def stop(self) -> None:
        pass


def _manager() -> AuthManager:
    return AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "admin",
                        "role": "ADMIN",
                        "token_sha256": hash_token("admin-token"),
                    },
                    {
                        "subject": "supervisor",
                        "role": "SUPERVISOR",
                        "token_sha256": hash_token("supervisor-token"),
                    },
                ],
            }
        )
    )


def test_runtime_endpoint_requires_bearer_token() -> None:
    app = create_live_app(
        FakeRuntime(),
        autostart=False,
        auth=_manager(),
    )
    client = TestClient(app)

    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v1/runtime/health").status_code == 401
    response = client.get(
        "/api/v1/runtime/health",
        headers={"Authorization": "Bearer supervisor-token"},
    )
    assert response.status_code == 200


def test_metrics_require_metrics_permission() -> None:
    app = create_live_app(
        FakeRuntime(),
        autostart=False,
        auth=_manager(),
    )
    client = TestClient(app)

    denied = client.get(
        "/metrics",
        headers={"Authorization": "Bearer supervisor-token"},
    )
    assert denied.status_code == 403

    allowed = client.get(
        "/metrics",
        headers={"Authorization": "Bearer admin-token"},
    )
    assert allowed.status_code == 200


def test_websocket_rejects_missing_token() -> None:
    app = create_live_app(
        FakeRuntime(),
        autostart=False,
        auth=_manager(),
    )
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/realtime"):
            pass
    assert exc.value.code == 4401


def test_websocket_accepts_query_token() -> None:
    app = create_live_app(
        FakeRuntime(),
        autostart=False,
        auth=_manager(),
    )
    client = TestClient(app)

    with client.websocket_connect(
        "/api/v1/realtime?access_token=supervisor-token"
    ):
        pass
