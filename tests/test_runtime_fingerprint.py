import hashlib

from video_pose.runtime_config import load_analysis_config
from video_pose.runtime_fingerprint import build_runtime_fingerprint
from video_pose.video_manifest import load_manifest


def test_runtime_fingerprint_hashes_critical_small_artifacts() -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    fingerprint = build_runtime_fingerprint(
        loaded,
        manifest,
    )

    expected = hashlib.sha256(
        loaded.path.read_bytes()
    ).hexdigest()
    assert fingerprint.config_sha256 == expected
    assert fingerprint.manifest_sha256 is not None
    assert fingerprint.rules_sha256 is not None
    assert fingerprint.planar_calibration_sha256 is not None
    assert fingerprint.zones_sha256 is not None
    assert fingerprint.capture_backend == "opencv"
    assert fingerprint.timestamp_source == "arrival"
    assert fingerprint.sync_tolerance_ms == manifest.sync_tolerance_ms
    assert fingerprint.camera_clock_offsets_ms == {
        camera.camera_id: camera.clock_offset_ms
        for camera in manifest.cameras
        if camera.enabled
    }


def test_native_fingerprint_records_pts_timebase() -> None:
    loaded = load_analysis_config(
        "configs/live-gstreamer-native-demo.yaml"
    )
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    fingerprint = build_runtime_fingerprint(
        loaded,
        manifest,
    )
    assert fingerprint.capture_backend == "gstreamer-native"
    assert fingerprint.timestamp_source == "pts"
