from types import SimpleNamespace

from video_pose.live_health import LiveHealthSnapshot, RuntimeHealthSnapshot
from video_pose.resilient_store import ResilientSessionStore
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


class FlappingStore:
    def __init__(self) -> None:
        self.available = False

    def list_sessions(self, _limit=100):
        if not self.available:
            raise RuntimeError("db unavailable")
        return []


def _config():
    loaded = load_analysis_config("configs/offline-demo.yaml")
    policy = loaded.config.readiness
    policy.enabled = True
    policy.require_all_cameras_online = False
    policy.require_sync = False
    policy.require_runtime_assets = False
    policy.require_storage_headroom = False
    policy.require_persistence = True
    policy.block_persistence_degraded = True
    policy.block_audit_degraded = False
    return loaded


def test_readiness_recovers_after_persistence_probe_succeeds() -> None:
    backend = FlappingStore()
    repository = ResilientSessionStore(backend)

    blocked = evaluate_session_readiness(
        _config(),
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=repository,
    )
    failed = {
        check.name
        for check in blocked.checks
        if not check.passed
    }
    assert "persistence-health" in failed
    assert blocked.ready is False

    backend.available = True
    recovered = evaluate_session_readiness(
        _config(),
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=repository,
    )
    assert recovered.ready is True
