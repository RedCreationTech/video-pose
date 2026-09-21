from types import SimpleNamespace

from video_pose.live_health import (
    LiveHealthSnapshot,
    ModelWarmupHealthSnapshot,
    RuntimeHealthSnapshot,
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

    def __init__(self, status: str, latency_ms: float):
        self._health = ModelWarmupHealthSnapshot(
            enabled=True,
            status=status,
            latency_ms=latency_ms,
        )

    def warmup_health(self):
        return self._health


def _config():
    loaded = load_analysis_config("configs/offline-demo.yaml")
    policy = loaded.config.readiness
    policy.enabled = True
    policy.require_all_cameras_online = False
    policy.require_sync = False
    policy.require_runtime_assets = False
    policy.require_storage_headroom = False
    policy.require_model_warmup = True
    loaded.config.model_warmup.enabled = True
    loaded.config.model_warmup.max_latency_ms = 1000
    return loaded


def test_readiness_requires_successful_model_warmup() -> None:
    passed = evaluate_session_readiness(
        _config(),
        hub=FakeHub(),
        model_pool=FakePool("PASS", 500),
        repository=None,
    )
    assert passed.ready is True

    failed = evaluate_session_readiness(
        _config(),
        hub=FakeHub(),
        model_pool=FakePool("FAIL", 200),
        repository=None,
    )
    check = next(
        item
        for item in failed.checks
        if item.name == "model-warmup"
    )
    assert check.passed is False
    assert failed.ready is False
