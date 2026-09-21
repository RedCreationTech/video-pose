from pathlib import Path

from video_pose.doctor import build_doctor_report
from video_pose.model_release import (
    build_model_release_manifest,
    write_model_release_manifest,
)
from video_pose.runtime_config import load_analysis_config


def test_doctor_validates_model_release(
    tmp_path: Path,
) -> None:
    detector = tmp_path / "detector.pt"
    detector.write_bytes(b"detector")
    manifest_file = tmp_path / "manifest.yaml"
    rules_file = tmp_path / "rules.yaml"
    manifest_file.write_text("x", encoding="utf-8")
    rules_file.write_text("x", encoding="utf-8")

    base_config = tmp_path / "base.yaml"
    base_config.write_text(
        f"""
manifest: {manifest_file}
rules: {rules_file}
detector:
  weights: {detector}
  device: cpu
pose: null
""".strip(),
        encoding="utf-8",
    )
    release = build_model_release_manifest(
        load_analysis_config(base_config),
        release_id="doctor-release",
    )
    release_path = write_model_release_manifest(
        release,
        tmp_path / "model-release.json",
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
  manifest: {release_path}
  verify_on_doctor: true
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
    assert check.status == "PASS"

    detector.write_bytes(b"changed")
    failed = build_doctor_report(
        config,
        module_exists=lambda _name: True,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    failed_check = next(
        item
        for item in failed.checks
        if item.name == "model-release"
    )
    assert failed_check.status == "FAIL"
