from types import SimpleNamespace

from video_pose.live_health import LiveHealthSnapshot, RuntimeHealthSnapshot
from video_pose.resilient_store import (
    ReconciliationHealth,
    ReconciliationStatus,
)
from video_pose.runtime_config import load_analysis_config
from video_pose.session_readiness import evaluate_session_readiness


class FakeHub:
    running = True
    manifest = SimpleNamespace(cameras=[])

    def health_snapshot(self):
        return LiveHealthSnapshot(
            cameras=[],
            runtime=RuntimeHealthSnapshot(),
            ready=True,
        )


class FakePool:
    loaded = True


class FakeRepository:
    def probe(self):
        return None

    def health(self):
        return SimpleNamespace(
            status="READY",
            last_error=None,
        )

    def reconciliation_health(self):
        return ReconciliationHealth(
            status=ReconciliationStatus.DIRTY,
            incomplete_count=1,
            last_error="reconciliation required",
        )


def test_readiness_blocks_dirty_reconciliation() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    policy = loaded.config.readiness
    policy.enabled = True
    policy.require_all_cameras_online = False
    policy.require_sync = False
    policy.require_runtime_assets = False
    policy.require_storage_headroom = False
    policy.require_persistence = True
    policy.block_persistence_degraded = True
    policy.require_persistence_reconciled = True
    policy.block_audit_degraded = False

    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=FakeRepository(),
    )
    check = next(
        item
        for item in report.checks
        if item.name == "persistence-reconciliation"
    )
    assert check.passed is False
    assert report.ready is False
