from pathlib import Path

from video_pose.model_release import (
    build_model_release_manifest,
    write_model_release_manifest,
)
from video_pose.runtime_config import load_analysis_config
from video_pose.runtime_fingerprint import build_runtime_fingerprint
from video_pose.video_manifest import load_manifest


def test_runtime_fingerprint_records_model_release(
    tmp_path: Path,
) -> None:
    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"detector")
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(
        """
session_id: s1
workstation_id: ws1
cameras:
  - {camera_id: f, position: FRONT, uri: rtsp://f}
  - {camera_id: r, position: REAR, uri: rtsp://r}
  - {camera_id: l, position: LEFT, uri: rtsp://l}
  - {camera_id: x, position: RIGHT, uri: rtsp://x}
""".strip(),
        encoding="utf-8",
    )
    rules = tmp_path / "rules.yaml"
    rules.write_text("x", encoding="utf-8")
    base = tmp_path / "base.yaml"
    base.write_text(
        f"""
manifest: {manifest_file}
rules: {rules}
detector:
  weights: {detector}
  device: cpu
pose: null
""".strip(),
        encoding="utf-8",
    )
    release = build_model_release_manifest(
        load_analysis_config(base),
        release_id="release-abc",
    )
    release_path = write_model_release_manifest(
        release,
        tmp_path / "release.json",
    )
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text(
        base.read_text(encoding="utf-8")
        + f"""
model_release:
  enabled: true
  manifest: {release_path}
""",
        encoding="utf-8",
    )
    loaded = load_analysis_config(runtime)
    fingerprint = build_runtime_fingerprint(
        loaded,
        load_manifest(manifest_file),
    )
    assert fingerprint.model_release_id == "release-abc"
    assert fingerprint.model_release_manifest_sha256 is not None
    assert fingerprint.model_artifact_sha256["detector"] == (
        release.artifacts[0].sha256
    )
