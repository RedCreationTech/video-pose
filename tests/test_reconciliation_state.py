from pathlib import Path

from video_pose.resilient_store import (
    PersistenceStatus,
    ReconciliationStatus,
    ResilientSessionStore,
)


class FlappingStore:
    def __init__(self) -> None:
        self.available = True
        self.fail_writes = False

    def list_sessions(self, _limit=100):
        if not self.available:
            raise RuntimeError("db unavailable")
        return []

    def record_update(self, _session_id, _payload):
        if self.fail_writes:
            raise RuntimeError("write failed")


def test_write_failure_marks_reconciliation_dirty_after_connectivity_recovers(
    tmp_path: Path,
) -> None:
    backend = FlappingStore()
    store = ResilientSessionStore(backend)
    store.reconcile(str(tmp_path / "empty-audit"))
    assert (
        store.reconciliation_health().status
        == ReconciliationStatus.READY
    )

    backend.fail_writes = True
    store.record_update("s1", {"actions": []})
    assert store.health().status == PersistenceStatus.DEGRADED
    assert (
        store.reconciliation_health().status
        == ReconciliationStatus.DIRTY
    )

    backend.fail_writes = False
    store.probe()
    assert store.health().status == PersistenceStatus.READY
    assert (
        store.reconciliation_health().status
        == ReconciliationStatus.DIRTY
    )
