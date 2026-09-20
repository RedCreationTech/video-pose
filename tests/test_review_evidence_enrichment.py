from types import SimpleNamespace

from video_pose.persistent_session_controller import (
    PersistentLiveSessionController,
)
from video_pose.runtime_config import load_analysis_config


class FakeRepository:
    def list_pending_reviews(self, limit=100):
        return [
            {
                "id": 1,
                "session_id": "s1",
                "rule_id": "R1",
                "step_code": "S010",
                "event_id": "a1",
                "review_status": "UNREVIEWED",
            },
            {
                "id": 2,
                "session_id": "s1",
                "rule_id": "R2",
                "step_code": "S020",
                "event_id": "a2",
                "review_status": "UNREVIEWED",
            },
        ][:limit]


class FakeHub:
    def __init__(self):
        self.calls = 0

    def list_evidence(self, session_id):
        self.calls += 1
        return [
            {
                "evidence_id": "ev1",
                "session_id": session_id,
                "rule_id": "R1",
                "step_code": "S010",
                "event_id": "a1",
                "status": "COMPLETE",
            }
        ]


def test_pending_review_is_enriched_with_matching_evidence(tmp_path):
    hub = FakeHub()
    controller = PersistentLiveSessionController(
        load_analysis_config("configs/offline-demo.yaml"),
        hub=hub,
        audit_root=tmp_path,
        repository=FakeRepository(),
    )
    reviews = controller.list_pending_reviews()
    assert reviews[0]["evidence"][0]["evidence_id"] == "ev1"
    assert reviews[1]["evidence"] == []
    assert hub.calls == 1
