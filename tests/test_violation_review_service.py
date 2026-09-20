from fastapi.testclient import TestClient

from video_pose.auth import AuthConfiguration, AuthManager, hash_token
from video_pose.live_broker import LiveEventBroker
from video_pose.live_health import LiveHealthRegistry
from video_pose.live_service import create_managed_live_app


class FakeController:
    def __init__(self) -> None:
        self.health = LiveHealthRegistry([])
        self.review_calls = []
        self.callback = None

    def set_event_callback(self, callback):
        self.callback = callback

    def health_snapshot(self):
        return self.health.snapshot()

    def list_pending_reviews(self, limit=100):
        return [{"id": 7, "review_status": "UNREVIEWED", "limit": limit}]

    def review_violation(
        self,
        session_id,
        violation_id,
        request,
        *,
        reviewer,
    ):
        self.review_calls.append(
            (session_id, violation_id, request.decision.value, reviewer)
        )
        return {
            "id": violation_id,
            "session_id": session_id,
            "review_status": request.decision.value,
            "reviewed_by": reviewer,
        }


def _auth() -> AuthManager:
    return AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "reviewer-1",
                        "role": "REVIEWER",
                        "token_sha256": hash_token("review-token"),
                    },
                    {
                        "subject": "operator-1",
                        "role": "OPERATOR",
                        "token_sha256": hash_token("operator-token"),
                    },
                ],
            }
        )
    )


def test_reviewer_can_list_and_review_violations() -> None:
    controller = FakeController()
    app = create_managed_live_app(
        controller,
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer review-token"}

    pending = client.get("/api/v1/reviews/pending", headers=headers)
    assert pending.status_code == 200
    assert pending.json()[0]["id"] == 7

    reviewed = client.post(
        "/api/v1/sessions/s1/violations/7/review",
        headers=headers,
        json={
            "decision": "DISMISSED",
            "comment": "occlusion false positive",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "DISMISSED"
    assert controller.review_calls == [
        ("s1", 7, "DISMISSED", "reviewer-1")
    ]


def test_operator_cannot_review_violation() -> None:
    app = create_managed_live_app(
        FakeController(),
        broker=LiveEventBroker(),
        autostart=False,
        auth=_auth(),
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/sessions/s1/violations/7/review",
        headers={"Authorization": "Bearer operator-token"},
        json={"decision": "CONFIRMED"},
    )
    assert response.status_code == 403
