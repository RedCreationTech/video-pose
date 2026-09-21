from pathlib import Path
from types import SimpleNamespace

from video_pose.live_health import (
    LiveHealthSnapshot,
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


def test_readiness_checks_real_storage_headroom(
    tmp_path: Path,
) -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.readiness.enabled = True
    loaded.config.readiness.require_all_cameras_online = False
    loaded.config.readiness.require_sync = False
    loaded.config.readiness.require_storage_headroom = True
    loaded.config.readiness.min_storage_free_ratio = 0.0
    loaded.config.readiness.min_storage_free_gb = 0.0

    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=None,
        audit_root=tmp_path / "not-created-yet",
    )
    storage_checks = [
        check
        for check in report.checks
        if check.name.startswith("storage:audit:")
    ]
    assert len(storage_checks) == 2
    assert all(check.passed for check in storage_checks)
