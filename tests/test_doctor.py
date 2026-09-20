from pathlib import Path

from video_pose.doctor import build_doctor_report

ROOT = Path(__file__).resolve().parents[1]


def test_doctor_reports_missing_runtime_assets() -> None:
    report = build_doctor_report(
        ROOT / "configs/offline-demo.yaml",
        module_exists=lambda _name: True,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    failed_names = {
        check.name
        for check in report.checks
        if check.status == "FAIL"
    }
    assert "detector-weights" in failed_names
    assert "pose-checkpoint" in failed_names
    assert report.passed is False


def test_doctor_can_pass_minimal_fixture_config(tmp_path: Path) -> None:
    for name in ("manifest.yaml", "rules.yaml", "weights.pt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        """
manifest: manifest.yaml
rules: rules.yaml
detector:
  weights: weights.pt
  device: cpu
pose: null
""".strip(),
        encoding="utf-8",
    )
    report = build_doctor_report(
        config,
        module_exists=lambda _name: True,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    assert report.passed is True
