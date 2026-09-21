import zipfile
from pathlib import Path

from video_pose.acceptance_bundle import (
    create_acceptance_bundle,
    verify_acceptance_bundle,
)
from video_pose.doctor import (
    CheckStatus,
    DoctorCheck,
    DoctorReport,
)
from video_pose.release_acceptance import (
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


def _acceptance(tmp_path: Path, *, soak: bool) -> Path:
    report = run_release_acceptance(
        config_path=ROOT / "configs/offline-demo.yaml",
        golden_dataset=(
            ROOT / "datasets/golden-v1/manifest.yaml"
        ),
        fault_scenarios=discover_fault_scenarios(
            ROOT / "fixtures/faults"
        ),
        soak_report_path=(
            ROOT / "fixtures/acceptance/managed-soak-pass.json"
            if soak
            else None
        ),
        quick=not soak,
        doctor_builder=_doctor,
    )
    path = tmp_path / "acceptance.json"
    path.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def test_acceptance_bundle_round_trip(tmp_path: Path) -> None:
    acceptance = _acceptance(tmp_path, soak=True)
    extra = tmp_path / "model-release.json"
    extra.write_text('{"release_id":"r1"}\n', encoding="utf-8")
    bundle = tmp_path / "release-bundle.zip"

    result = create_acceptance_bundle(
        acceptance_report_path=acceptance,
        output_path=bundle,
        extra_paths=[extra],
    )
    assert Path(result.bundle_path).exists()
    assert Path(result.sha256_sidecar_path).exists()
    assert result.manifest.production_ready is True

    verification = verify_acceptance_bundle(bundle)
    assert verification.passed is True
    assert verification.entries_verified == len(
        result.manifest.entries
    )


def test_bundle_rejects_not_ready_report_by_default(
    tmp_path: Path,
) -> None:
    acceptance = _acceptance(tmp_path, soak=False)
    try:
        create_acceptance_bundle(
            acceptance_report_path=acceptance,
            output_path=tmp_path / "quick.zip",
        )
    except ValueError as exc:
        assert "not production_ready" in str(exc)
    else:
        raise AssertionError("not-ready acceptance should be rejected")


def test_bundle_verifier_detects_tampered_entry(
    tmp_path: Path,
) -> None:
    acceptance = _acceptance(tmp_path, soak=True)
    bundle = tmp_path / "release.zip"
    create_acceptance_bundle(
        acceptance_report_path=acceptance,
        output_path=bundle,
    )

    tampered = tmp_path / "tampered.zip"
    changed = False
    with zipfile.ZipFile(bundle, "r") as source:
        with zipfile.ZipFile(tampered, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if (
                    not changed
                    and info.filename.startswith("artifacts/")
                ):
                    data += b"tampered"
                    changed = True
                target.writestr(info, data)

    verification = verify_acceptance_bundle(tampered)
    assert verification.passed is False
    assert any(
        "mismatch" in failure
        for failure in verification.failures
    )
