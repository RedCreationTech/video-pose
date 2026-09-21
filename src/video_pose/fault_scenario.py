from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from .contracts import ReplayResult, Violation
from .live_health import (
    CameraHealthSnapshot,
    CameraState,
    LiveHealthSnapshot,
    RuntimeHealthSnapshot,
    SyncHealthSnapshot,
)
from .realtime_rules import RealtimeRuleSession
from .rules import RuleEngine
from .runtime_config import SessionQualityRuntimeConfig
from .session_quality import SessionQualityMonitor


class FaultCameraState(BaseModel):
    state: CameraState = CameraState.ONLINE
    last_frame_age_ms: float = Field(default=0.0, ge=0.0)


class FaultSyncState(BaseModel):
    reference_frames_total: int = Field(default=0, ge=0)
    emitted_total: int = Field(default=0, ge=0)
    miss_total: int = Field(default=0, ge=0)
    skew_p99_ms: float = Field(default=0.0, ge=0.0)
    camera_drift_ms_per_minute: dict[str, float] = Field(
        default_factory=dict
    )


class FaultStep(BaseModel):
    at_ms: float = Field(ge=0.0)
    cameras: dict[str, FaultCameraState] = Field(
        default_factory=dict
    )
    sync: FaultSyncState | None = None


class FaultExpectation(BaseModel):
    violation_types: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    final_session_passed: bool


class FaultScenario(BaseModel):
    scenario_id: str
    session_id: str
    rules: str
    camera_ids: list[str]
    quality: SessionQualityRuntimeConfig
    steps: list[FaultStep]
    expect: FaultExpectation

    @model_validator(mode="after")
    def steps_are_monotonic(self) -> FaultScenario:
        timestamps = [step.at_ms for step in self.steps]
        if timestamps != sorted(timestamps):
            raise ValueError("fault steps must be sorted by at_ms")
        if not timestamps:
            raise ValueError("fault scenario requires at least one step")
        return self


class FaultScenarioEvaluation(BaseModel):
    scenario_id: str
    matched_expectations: bool
    final_session_passed: bool
    violations: list[Violation]
    final_result: ReplayResult
    failures: list[str] = Field(default_factory=list)


class FaultScenarioRunner:
    """Drive SessionQualityMonitor with deterministic synthetic health."""

    def __init__(
        self,
        scenario: FaultScenario,
        engine: RuleEngine,
    ) -> None:
        self.scenario = scenario
        self.monitor = SessionQualityMonitor(
            scenario.quality,
            camera_ids=scenario.camera_ids,
        )
        self.rules = RealtimeRuleSession(
            engine,
            session_id=scenario.session_id,
        )
        self._cameras = {
            camera_id: FaultCameraState()
            for camera_id in scenario.camera_ids
        }
        self._sync: FaultSyncState | None = None

    def run(self) -> FaultScenarioEvaluation:
        for step in self.scenario.steps:
            self._apply_step(step)
            snapshot = self._snapshot(step.at_ms)
            incidents = self.monitor.observe(
                snapshot,
                now_monotonic_ms=step.at_ms,
            )
            for violation in incidents:
                self.rules.record_external_violation(
                    violation,
                    now_ms=round(step.at_ms),
                )

        final_result = self.rules.tick(
            round(self.scenario.steps[-1].at_ms)
        ).result
        violations = [
            violation.model_copy(deep=True)
            for violation in final_result.violations
        ]
        failures = self._expectation_failures(
            violations,
            final_result,
        )
        return FaultScenarioEvaluation(
            scenario_id=self.scenario.scenario_id,
            matched_expectations=not failures,
            final_session_passed=final_result.passed,
            violations=violations,
            final_result=final_result,
            failures=failures,
        )

    def _apply_step(self, step: FaultStep) -> None:
        for camera_id, state in step.cameras.items():
            if camera_id not in self._cameras:
                raise ValueError(
                    f"unknown scenario camera: {camera_id}"
                )
            self._cameras[camera_id] = state
        if step.sync is not None:
            self._sync = step.sync

    def _snapshot(self, at_ms: float) -> LiveHealthSnapshot:
        cameras = [
            CameraHealthSnapshot(
                camera_id=camera_id,
                state=state.state,
                last_frame_monotonic_ms=max(
                    0.0,
                    at_ms - state.last_frame_age_ms,
                ),
            )
            for camera_id, state in sorted(self._cameras.items())
        ]
        sync = (
            SyncHealthSnapshot(
                reference_frames_total=(
                    self._sync.reference_frames_total
                ),
                emitted_total=self._sync.emitted_total,
                miss_total=self._sync.miss_total,
                skew_p99_ms=self._sync.skew_p99_ms,
                camera_drift_ms_per_minute=dict(
                    self._sync.camera_drift_ms_per_minute
                ),
            )
            if self._sync is not None
            else None
        )
        ready = bool(cameras) and all(
            camera.state == CameraState.ONLINE
            for camera in cameras
        )
        return LiveHealthSnapshot(
            cameras=cameras,
            runtime=RuntimeHealthSnapshot(),
            sync=sync,
            ready=ready,
        )

    def _expectation_failures(
        self,
        violations: list[Violation],
        final_result: ReplayResult,
    ) -> list[str]:
        failures: list[str] = []
        actual_types = [
            violation.type for violation in violations
        ]
        actual_rule_ids = [
            violation.rule_id for violation in violations
        ]
        if actual_types != self.scenario.expect.violation_types:
            failures.append(
                "violation_types mismatch: "
                f"expected={self.scenario.expect.violation_types}, "
                f"actual={actual_types}"
            )
        if (
            self.scenario.expect.rule_ids
            and actual_rule_ids != self.scenario.expect.rule_ids
        ):
            failures.append(
                "rule_ids mismatch: "
                f"expected={self.scenario.expect.rule_ids}, "
                f"actual={actual_rule_ids}"
            )
        if (
            final_result.passed
            != self.scenario.expect.final_session_passed
        ):
            failures.append(
                "final_session_passed mismatch: "
                f"expected={self.scenario.expect.final_session_passed}, "
                f"actual={final_result.passed}"
            )
        return failures


def load_fault_scenario(
    path: str | Path,
) -> tuple[FaultScenario, Path]:
    scenario_path = Path(path).resolve()
    payload = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    scenario = FaultScenario.model_validate(payload)
    rules_path = Path(scenario.rules)
    if not rules_path.is_absolute():
        rules_path = (
            scenario_path.parent / rules_path
        ).resolve()
    return scenario, rules_path


def run_fault_scenario(
    path: str | Path,
) -> FaultScenarioEvaluation:
    scenario, rules_path = load_fault_scenario(path)
    return FaultScenarioRunner(
        scenario,
        RuleEngine.from_yaml(rules_path),
    ).run()
