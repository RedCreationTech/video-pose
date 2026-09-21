from pathlib import Path

from video_pose.resilient_store import (
    ReconciliationStatus,
    ResilientSessionStore,
)


class MinimalStore:
    def list_sessions(self, _limit=100):
        return []


def test_empty_audit_reconciliation_sets_ready(
    tmp_path: Path,
) -> None:
    store = ResilientSessionStore(MinimalStore())
    report = store.reconcile(str(tmp_path / "audit"))
    assert report.failed_count == 0
    assert report.incomplete_count == 0
    health = store.reconciliation_health()
    assert health.status == ReconciliationStatus.READY
    assert health.last_completed_at is not None
