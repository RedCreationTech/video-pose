from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .doctor import DoctorReport, build_doctor_report
from .fault_scenario import (
    FaultScenarioEvaluation,
    run_fault_scenario,
)
from .golden import (
    GoldenEvaluationReport,
    evaluate_golden_dataset,
)
from .managed_soak import ManagedSoakReport
from .runtime_config import load_analysis_config
from .runtime_fingerprint import sha256_file
from .runtime_identity import (
    RuntimeReleaseIdentity,
    build_runtime_release_identity,
)
from .video_manifest import load_manifest


class ReleaseAcceptanceThresholds(BaseModel):
    min_action_f1: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
    )
    min_violation_f1: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
    )
    min_session_accuracy: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
    )
    min_soak_hours: float = Field(default=72.0, gt=0.0)
    min_soak_completed_sessions: int = Field(
        default=2,
        ge=1,
    )


class AcceptanceArtifact(BaseModel):
    kind: str
    path: str
    sha256: str | None


class ReleaseAcceptanceReport(BaseModel):
    generated_at: str
    mode: str
    release_identity: RuntimeReleaseIdentity
    doctor: DoctorReport
    golden: GoldenEvaluationReport
    faults: list[FaultScenarioEvaluation]
    managed_soak: ManagedSoakReport | None = None
    thresholds: ReleaseAcceptanceThresholds
    artifacts: list[AcceptanceArtifact] = Field(
        default_factory=list
    )
    quick_checks_passed: bool
    production_ready: bool
    quick_failures: list[str] = Field(default_factory=list)
    production_failures: list[str] = Field(
        default_factory=list
    )


def discover_fault_scenarios(
    directory: str | Path,
) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    return sorted(root.glob("*.yaml"))


def load_managed_soak_report(
    path: str | Path,
) -> ManagedSoakReport:
    return ManagedSoakReport.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def _artifact(kind: str, path: str | Path) -> AcceptanceArtifact:
    resolved = Path(path).resolve()
    return AcceptanceArtifact(
        kind=kind,
        path=str(resolved),
        sha256=sha256_file(resolved),
    )


def run_release_acceptance(
    *,
    config_path: str | Path,
    golden_dataset: str | Path,
    fault_scenarios: list[str | Path],
    soak_report_path: str | Path | None = None,
    quick: bool = False,
    thresholds: ReleaseAcceptanceThresholds | None = None,
    doctor_builder: Callable[[str | Path], DoctorReport] = (
        build_doctor_report
    ),
    golden_evaluator: Callable[
        [str | Path],
        GoldenEvaluationReport,
    ] = evaluate_golden_dataset,
    fault_runner: Callable[
        [str | Path],
        FaultScenarioEvaluation,
    ] = run_fault_scenario,
) -> ReleaseAcceptanceReport:
    limits = thresholds or ReleaseAcceptanceThresholds()
    loaded = load_analysis_config(config_path)
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )
    identity = build_runtime_release_identity(
        loaded,
        manifest,
    )

    doctor = doctor_builder(config_path)
    golden = golden_evaluator(golden_dataset)
    faults = [
        fault_runner(path)
        for path in fault_scenarios
    ]

    soak = (
        load_managed_soak_report(soak_report_path)
        if soak_report_path is not None
        else None
    )

    quick_failures: list[str] = []
    if not doctor.passed:
        quick_failures.append("doctor_failed")
    if golden.actions.f1 < limits.min_action_f1:
        quick_failures.append(
            f"action_f1={golden.actions.f1:.6f} "
            f"< {limits.min_action_f1:.6f}"
        )
    if golden.violations.f1 < limits.min_violation_f1:
        quick_failures.append(
            f"violation_f1={golden.violations.f1:.6f} "
            f"< {limits.min_violation_f1:.6f}"
        )
    if (
        golden.session_pass_accuracy
        < limits.min_session_accuracy
    ):
        quick_failures.append(
            "session_pass_accuracy="
            f"{golden.session_pass_accuracy:.6f} "
            f"< {limits.min_session_accuracy:.6f}"
        )
    if not faults:
        quick_failures.append("fault_scenarios_missing")
    for fault in faults:
        if not fault.matched_expectations:
            quick_failures.append(
                f"fault_failed:{fault.scenario_id}"
            )

    production_failures = list(quick_failures)
    if soak is None:
        production_failures.append("managed_soak_report_missing")
    else:
        if not soak.passed:
            production_failures.append("managed_soak_failed")
        soak_hours = soak.health.duration_s / 3600.0
        if soak_hours < limits.min_soak_hours:
            production_failures.append(
                f"managed_soak_hours={soak_hours:.6f} "
                f"< {limits.min_soak_hours:.6f}"
            )
        if (
            soak.sessions_completed
            < limits.min_soak_completed_sessions
        ):
            production_failures.append(
                "managed_soak_sessions_completed="
                f"{soak.sessions_completed} "
                f"< {limits.min_soak_completed_sessions}"
            )

    artifacts = [
        _artifact("runtime-config", config_path),
        _artifact("golden-dataset", golden_dataset),
    ]
    artifacts.extend(
        _artifact("fault-scenario", path)
        for path in fault_scenarios
    )
    if soak_report_path is not None:
        artifacts.append(
            _artifact("managed-soak-report", soak_report_path)
        )

    return ReleaseAcceptanceReport(
        generated_at=datetime.now(UTC).isoformat(),
        mode="quick" if quick else "production",
        release_identity=identity,
        doctor=doctor,
        golden=golden,
        faults=faults,
        managed_soak=soak,
        thresholds=limits,
        artifacts=artifacts,
        quick_checks_passed=not quick_failures,
        production_ready=not production_failures,
        quick_failures=quick_failures,
        production_failures=production_failures,
    )
