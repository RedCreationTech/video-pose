from video_pose.resilient_store import (
    PersistenceStatus,
    ResilientSessionStore,
)


class FlappingStore:
    def __init__(self) -> None:
        self.available = False

    def list_sessions(self, _limit=100):
        if not self.available:
            raise RuntimeError("db unavailable")
        return []

    def create_schema(self):
        pass

    def start_session(self, _metadata):
        pass

    def record_update(self, _session_id, _payload):
        pass

    def finalize(self, _session_id, _payload, *, status):
        del status

    def get_session(self, _session_id):
        return None

    def list_pending_reviews(self, _limit=100):
        return []

    def review_violation(self, *_args, **_kwargs):
        return None

    def review_violation_by_identity(self, *_args, **_kwargs):
        return None


def test_resilient_store_recovers_current_status_but_keeps_counters() -> None:
    backend = FlappingStore()
    store = ResilientSessionStore(backend)

    degraded = store.probe()
    assert degraded.status == PersistenceStatus.DEGRADED
    assert degraded.read_errors_total == 1

    backend.available = True
    recovered = store.probe()
    assert recovered.status == PersistenceStatus.READY
    assert recovered.read_errors_total == 1
    assert recovered.last_error is None
