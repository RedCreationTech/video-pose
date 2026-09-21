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


def _base_config():
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.readiness.enabled = True
    loaded.config.readiness.require_all_cameras_online = False
    loaded.config.readiness.require_sync = False
    loaded.config.readiness.require_storage_headroom = False
    loaded.config.calibration_health.enabled = True
    loaded.config.calibration_health.calibration = (
        "../fixtures/calibration/perspective-demo.yaml"
    )
    loaded.config.calibration_health.control_points = (
        "../fixtures/calibration/control-points-demo.yaml"
    )
    return loaded


def test_readiness_passes_calibration_health_fixture() -> None:
    loaded = _base_config()
    loaded.config.calibration_health.max_rmse = 0.001
    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=None,
    )
    health = next(
        check
        for check in report.checks
        if check.name == "calibration-health"
    )
    assert health.passed is True


def test_readiness_blocks_when_calibration_control_points_are_missing() -> None:
    loaded = _base_config()
    loaded.config.calibration_health.control_points = (
        "../fixtures/calibration/does-not-exist.yaml"
    )
    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(),
        model_pool=FakePool(),
        repository=None,
    )
    health = next(
        check
        for check in report.checks
        if check.name == "calibration-health"
    )
    assert health.passed is False
    assert report.ready is False
