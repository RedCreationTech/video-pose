from video_pose.runtime_config import load_analysis_config
from video_pose.runtime_fingerprint import build_runtime_fingerprint
from video_pose.video_manifest import load_manifest


def test_calibration_control_points_are_fingerprinted() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    loaded.config.calibration_health.enabled = True
    loaded.config.calibration_health.calibration = (
        "../fixtures/calibration/perspective-demo.yaml"
    )
    loaded.config.calibration_health.control_points = (
        "../fixtures/calibration/control-points-demo.yaml"
    )
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    fingerprint = build_runtime_fingerprint(
        loaded,
        manifest,
    )
    assert fingerprint.calibration_health_profile_sha256 is not None
    assert fingerprint.calibration_control_points_sha256 is not None
