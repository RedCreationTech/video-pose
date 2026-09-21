from pathlib import Path

from video_pose.doctor import build_doctor_report


def test_doctor_can_skip_model_release_hash_verification(
    tmp_path: Path,
) -> None:
    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"actual")
    manifest_file = tmp_path / "manifest.yaml"
    rules_file = tmp_path / "rules.yaml"
    release_file = tmp_path / "release.json"
    manifest_file.write_text("x", encoding="utf-8")
    rules_file.write_text("x", encoding="utf-8")
    release_file.write_text(
        """
{
  "schema_version": 1,
  "release_id": "r1",
  "created_at": "2026-09-21T00:00:00+00:00",
  "artifacts": [
    {
      "name": "detector",
      "role": "detector_weights",
      "path": "/does/not/exist.pt",
      "size_bytes": 99,
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    config = tmp_path / "runtime.yaml"
    config.write_text(
        f"""
manifest: {manifest_file}
rules: {rules_file}
detector:
  weights: {detector}
  device: cpu
pose: null
model_release:
  enabled: true
  manifest: {release_file}
  verify_on_doctor: false
""".strip(),
        encoding="utf-8",
    )
    report = build_doctor_report(
        config,
        module_exists=lambda _name: True,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    check = next(
        item
        for item in report.checks
        if item.name == "model-release"
    )
    assert check.status == "WARN"
    assert check.required is False
    assert report.passed is True
