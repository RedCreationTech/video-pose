from fastapi.testclient import TestClient

from video_pose.auth import AuthConfiguration, AuthManager, hash_token
from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry([])
        self.callback = None

    def set_event_callback(self, callback):
        self.callback = callback

    def health_snapshot(self):
        return self.health.snapshot()

    def list_evidence(self, session_id):
        return [{"evidence_id": "ev1", "session_id": session_id}]

    def evidence_manifest(self, session_id, evidence_id):
        if evidence_id != "ev1":
            return None
        return {
            "evidence_id": evidence_id,
            "session_id": session_id,
            "status": "COMPLETE",
        }

    def evidence_file(
        self,
        session_id,
        evidence_id,
        camera_id,
        filename,
    ):
        del session_id, evidence_id, camera_id, filename
        return b"jpeg-bytes"


def _auth() -> AuthManager:
    return AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "reviewer",
                        "role": "REVIEWER",
                        "token_sha256": hash_token("review-token"),
                    },
                    {
                        "subject": "operator",
                        "role": "OPERATOR",
                        "token_sha256": hash_token("operator-token"),
                    },
                ],
            }
        )
    )


def test_reviewer_can_read_evidence() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer review-token"}

    listing = client.get(
        "/api/v1/sessions/s1/evidence",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()[0]["evidence_id"] == "ev1"

    manifest = client.get(
        "/api/v1/sessions/s1/evidence/ev1",
        headers=headers,
    )
    assert manifest.status_code == 200

    image = client.get(
        "/api/v1/sessions/s1/evidence/ev1/files/front/0001.jpg",
        headers=headers,
    )
    assert image.status_code == 200
    assert image.content == b"jpeg-bytes"
    assert image.headers["content-type"].startswith("image/jpeg")


def test_operator_is_denied_evidence() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)
    response = client.get(
        "/api/v1/sessions/s1/evidence",
        headers={"Authorization": "Bearer operator-token"},
    )
    assert response.status_code == 403
