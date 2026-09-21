from pathlib import Path

from video_pose.doctor import build_doctor_report


def test_doctor_requires_mmcv_when_pose_is_enabled(
    tmp_path: Path,
) -> None:
    for name in (
        "manifest.yaml",
        "rules.yaml",
        "weights.pt",
        "pose.py",
        "pose.pth",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        """
manifest: manifest.yaml
rules: rules.yaml
detector:
  weights: weights.pt
  device: cpu
pose:
  enabled: true
  config: pose.py
  checkpoint: pose.pth
  device: cpu
""".strip(),
        encoding="utf-8",
    )

    def module_exists(name: str) -> bool:
        return name != "mmcv"

    report = build_doctor_report(
        config,
        module_exists=module_exists,
        binary_exists=lambda _name: True,
        include_cuda=False,
    )
    mmcv = next(
        check
        for check in report.checks
        if check.name == "python-module:mmcv"
    )
    assert mmcv.status == "FAIL"
    assert report.passed is False
