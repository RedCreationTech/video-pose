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


def test_managed_app_serves_self_contained_console() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)

    html = client.get("/console")
    css = client.get("/console/style.css")
    js = client.get("/console/app.js")

    assert html.status_code == 200
    assert "动作规范检测现场控制台" in html.text
    assert "Content-Security-Policy" in html.headers
    assert "script-src 'self'" in html.headers[
        "Content-Security-Policy"
    ]
    assert css.status_code == 200
    assert "--panel" in css.text
    assert js.status_code == 200
    assert "/api/v1/sessions/readiness" in js.text


def test_console_does_not_put_bearer_token_in_url() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
    )
    client = TestClient(app)
    js = client.get("/console/app.js").text

    assert "localStorage" not in js
    assert "access_token=" not in js
    assert "ws://" not in js
    assert "Authorization" in js
