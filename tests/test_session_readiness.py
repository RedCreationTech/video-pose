from types import SimpleNamespace

from video_pose.live_health import (
    CameraHealthSnapshot,
    CameraState,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from video_pose.runtime_config import load_analysis_config
from video_pose.session_readiness import evaluate_session_readiness
from video_pose.video_manifest import load_manifest


class FakeHub:
    running = True

    def __init__(self, manifest, health):
        self.manifest = manifest
        self._health = health

    def health_snapshot(self):
        return self._health


class FakePool:
    loaded = True


def _healthy_snapshot(manifest):
    return LiveHealthSnapshot(
        cameras=[
            CameraHealthSnapshot(
                camera_id=camera.camera_id,
                state=CameraState.ONLINE,
            )
            for camera in manifest.cameras
        ],
        runtime=RuntimeHealthSnapshot(),
        sync=SyncHealthSnapshot(
            reference_frames_total=100,
            emitted_total=95,
            miss_total=5,
            skew_p99_ms=8.0,
            camera_drift_ms_per_minute={
                camera.camera_id: 0.2
                for camera in manifest.cameras
            },
        ),
        ready=True,
    )


def test_readiness_passes_healthy_persistent_runtime() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.readiness.enabled = True
    loaded.config.readiness.min_sync_emitted_total = 10
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(
            manifest,
            _healthy_snapshot(manifest),
        ),
        model_pool=FakePool(),
        repository=SimpleNamespace(),
    )
    assert report.ready is True


def test_readiness_explains_camera_and_sync_failure() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.readiness.enabled = True
    loaded.config.readiness.min_sync_emitted_total = 10
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    snapshot = _healthy_snapshot(manifest)
    snapshot.cameras[0].state = CameraState.RECONNECTING
    assert snapshot.sync is not None
    snapshot.sync.skew_p99_ms = 40.0
    snapshot.sync.camera_drift_ms_per_minute["cam-left"] = 4.0

    report = evaluate_session_readiness(
        loaded,
        hub=FakeHub(manifest, snapshot),
        model_pool=FakePool(),
        repository=None,
    )
    failed = {
        check.name
        for check in report.checks
        if not check.passed
    }
    assert "cameras" in failed
    assert "sync-p99-skew" in failed
    assert "sync-clock-drift" in failed
    assert report.ready is False


def test_disabled_readiness_policy_never_blocks_start_gate() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    report = evaluate_session_readiness(
        loaded,
        hub=SimpleNamespace(),
        model_pool=None,
        repository=None,
    )
    assert report.policy_enabled is False
    assert report.ready is True
