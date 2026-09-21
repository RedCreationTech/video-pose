from pathlib import Path

from video_pose.model_release import (
    build_model_release_manifest,
    verify_model_release_manifest,
    write_model_release_manifest,
)
from video_pose.runtime_config import load_analysis_config


def _config(tmp_path: Path) -> Path:
    detector = tmp_path / "detector.pt"
    pose = tmp_path / "pose.pth"
    detector.write_bytes(b"detector-v1")
    pose.write_bytes(b"pose-v1")

    config = tmp_path / "runtime.yaml"
    config.write_text(
        f"""
manifest: manifest.yaml
rules: rules.yaml
detector:
  weights: {detector}
  device: cpu
pose:
  enabled: true
  config: pose.py
  checkpoint: {pose}
  device: cpu
""".strip(),
        encoding="utf-8",
    )
    return config


def test_model_release_detects_weight_tampering(
    tmp_path: Path,
) -> None:
    loaded = load_analysis_config(_config(tmp_path))
    manifest = build_model_release_manifest(
        loaded,
        release_id="r1",
    )
    assert [item.name for item in manifest.artifacts] == [
        "detector",
        "pose",
    ]
    assert verify_model_release_manifest(manifest).passed is True

    Path(manifest.artifacts[0].path).write_bytes(
        b"detector-tampered"
    )
    verification = verify_model_release_manifest(manifest)
    assert verification.passed is False
    detector = verification.artifacts[0]
    assert detector.exists is True
    assert detector.sha256_matches is False


def test_model_release_manifest_round_trip(
    tmp_path: Path,
) -> None:
    loaded = load_analysis_config(_config(tmp_path))
    manifest = build_model_release_manifest(
        loaded,
        release_id="site-release-42",
    )
    target = write_model_release_manifest(
        manifest,
        tmp_path / "model-release.json",
    )
    assert target.exists()
    assert "site-release-42" in target.read_text(encoding="utf-8")
