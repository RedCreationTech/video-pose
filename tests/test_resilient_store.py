from video_pose.resilient_store import (
    PersistenceStatus,
    ResilientSessionStore,
)
from video_pose.session_audit import SessionAuditMetadata


class FailingStore:
    def create_schema(self) -> None:
        raise RuntimeError("db unavailable")

    def start_session(self, _metadata) -> None:
        raise RuntimeError("db unavailable")

    def record_update(self, _session_id, _payload) -> None:
        raise RuntimeError("db unavailable")

    def finalize(self, _session_id, _payload, *, status) -> None:
        del status
        raise RuntimeError("db unavailable")

    def list_sessions(self, _limit=100):
        raise RuntimeError("db unavailable")

    def get_session(self, _session_id):
        raise RuntimeError("db unavailable")


def _metadata() -> SessionAuditMetadata:
    return SessionAuditMetadata(
        session_id="s1",
        operation="op",
        workstation_id="ws",
        rule_set_version=1,
        started_at="2026-09-20T00:00:00+00:00",
        config_path="/tmp/config.yaml",
        detector_weights="tools.pt",
    )


def test_resilient_store_never_raises_for_secondary_database() -> None:
    store = ResilientSessionStore(FailingStore())
    store.start_session(_metadata())
    store.record_update("s1", {"actions": []})
    store.finalize("s1", {"result": {}}, status="COMPLETED")
    assert store.list_sessions() == []
    assert store.get_session("s1") is None

    health = store.health()
    assert health.status == PersistenceStatus.DEGRADED
    assert health.write_errors_total == 3
    assert health.read_errors_total == 2
    assert health.last_error == "db unavailable"
