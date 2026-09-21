from pathlib import Path

from video_pose.doctor import build_doctor_report

ROOT = Path(__file__).resolve().parents[1]


def test_doctor_runs_calibration_health_when_enabled(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
manifest: {ROOT / "fixtures/replay/session-manifest.yaml"}
rules: {ROOT / "fixtures/rules/pick-place.yaml"}
detector:
  weights: {tmp_path / "weights.pt"}
  device: cpu
pose: null
calibration_health:
  enabled: true
  calibration: {ROOT / "fixtures/calibration/perspective-demo.yaml"}
  control_points: {ROOT / "fixtures/calibration/control-points-demo.yaml"}
  max_rmse: 0.001
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "weights.pt").write_text("x", encoding="utf-8")
    report = build_doctor_report(
        config,
        module_exists=lambda _name: True,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    check = next(
        item
        for item in report.checks
        if item.name == "calibration-health"
    )
    assert check.status == "PASS"
