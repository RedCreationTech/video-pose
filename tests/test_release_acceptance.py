from pathlib import Path

from video_pose.doctor import (
    CheckStatus,
    DoctorCheck,
    DoctorReport,
)
from video_pose.release_acceptance import (
    ReleaseAcceptanceThresholds,
    discover_fault_scenarios,
    run_release_acceptance,
)

ROOT = Path(__file__).resolve().parents[1]


def _doctor(_path) -> DoctorReport:
    return DoctorReport(
        checks=[
            DoctorCheck(
                name="fake",
                status=CheckStatus.PASS,
                required=True,
                detail="ok",
            )
        ]
    )


def test_release_acceptance_is_production_ready_with_72h_evidence() -> None:
    faults = discover_fault_scenarios(
        ROOT / "fixtures/faults"
    )
    report = run_release_acceptance(
        config_path=ROOT / "configs/offline-demo.yaml",
        golden_dataset=(
            ROOT / "datasets/golden-v1/manifest.yaml"
        ),
        fault_scenarios=faults,
        soak_report_path=(
            ROOT / "fixtures/acceptance/managed-soak-pass.json"
        ),
        thresholds=ReleaseAcceptanceThresholds(),
        doctor_builder=_doctor,
    )
    assert report.quick_checks_passed is True
    assert report.production_ready is True
    assert len(report.faults) >= 1
    assert all(
        fault.matched_expectations
        for fault in report.faults
    )
    assert all(
        artifact.sha256 is not None
        for artifact in report.artifacts
    )


def test_quick_mode_never_claims_production_ready_without_soak() -> None:
    report = run_release_acceptance(
        config_path=ROOT / "configs/offline-demo.yaml",
        golden_dataset=(
            ROOT / "datasets/golden-v1/manifest.yaml"
        ),
        fault_scenarios=discover_fault_scenarios(
            ROOT / "fixtures/faults"
        ),
        quick=True,
        doctor_builder=_doctor,
    )
    assert report.quick_checks_passed is True
    assert report.production_ready is False
    assert "managed_soak_report_missing" in (
        report.production_failures
    )


def test_short_soak_cannot_pass_production_gate(tmp_path: Path) -> None:
    source = (
        ROOT / "fixtures/acceptance/managed-soak-pass.json"
    ).read_text(encoding="utf-8")
    target = tmp_path / "short.json"
    target.write_text(
        source.replace(
            '"duration_s": 259200.0',
            '"duration_s": 3600.0',
        ),
        encoding="utf-8",
    )
    report = run_release_acceptance(
        config_path=ROOT / "configs/offline-demo.yaml",
        golden_dataset=(
            ROOT / "datasets/golden-v1/manifest.yaml"
        ),
        fault_scenarios=discover_fault_scenarios(
            ROOT / "fixtures/faults"
        ),
        soak_report_path=target,
        doctor_builder=_doctor,
    )
    assert report.production_ready is False
    assert any(
        "managed_soak_hours" in failure
        for failure in report.production_failures
    )
