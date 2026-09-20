from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .contracts import (
    ActionEvent,
    ReplayResult,
    RuleDefinition,
    RuleSet,
    StepDefinition,
    StepResult,
    StepState,
    Violation,
)


@dataclass(slots=True)
class _SessionState:
    steps: dict[str, StepResult]
    violations: list[Violation]


class RuleEngine:
    """Deterministic MVP rule engine for replay and contract stabilization."""

    def __init__(self, rule_set: RuleSet) -> None:
        self.rule_set = rule_set
        self._step_defs = {step.code: step for step in rule_set.steps}
        self._rules_by_action: dict[str, list[RuleDefinition]] = {}
        for rule in rule_set.rules:
            self._rules_by_action.setdefault(rule.action.value, []).append(rule)

    @classmethod
    def from_yaml(cls, path: str | Path) -> RuleEngine:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        return cls(RuleSet.model_validate(payload))

    def evaluate(self, events: Iterable[ActionEvent]) -> ReplayResult:
        ordered = sorted(
            events,
            key=lambda item: (item.sequence, item.started_at_ms, item.event_id),
        )
        if not ordered:
            raise ValueError("at least one action event is required")

        session_ids = {event.session_id for event in ordered}
        if len(session_ids) != 1:
            raise ValueError("all events must belong to the same session")

        state = _SessionState(
            steps={
                step.code: StepResult(
                    code=step.code,
                    state=StepState.READY if not step.predecessors else StepState.PENDING,
                )
                for step in self.rule_set.steps
            },
            violations=[],
        )

        seen_sequences: set[int] = set()
        seen_event_ids: set[str] = set()
        for event in ordered:
            if event.sequence in seen_sequences or event.event_id in seen_event_ids:
                continue
            seen_sequences.add(event.sequence)
            seen_event_ids.add(event.event_id)
            self._apply_event(state, event)
            self._refresh_ready_steps(state)

        self._finalize_missing_required_steps(state)
        score = self._score(state.violations)
        passed = not any(v.severity.value in {"MAJOR", "CRITICAL"} for v in state.violations)
        return ReplayResult(
            session_id=ordered[0].session_id,
            operation=self.rule_set.operation,
            rule_set_version=self.rule_set.version,
            steps=[state.steps[step.code] for step in self.rule_set.steps],
            violations=state.violations,
            score=score,
            passed=passed,
        )

    def _apply_event(self, state: _SessionState, event: ActionEvent) -> None:
        candidate_steps = [
            step
            for step in self.rule_set.steps
            if step.action == event.action
            and state.steps[step.code].state in {StepState.READY, StepState.ACTIVE}
        ]
        if not candidate_steps:
            return

        for step in candidate_steps:
            if event.confidence < step.min_confidence:
                state.steps[step.code] = StepResult(
                    code=step.code,
                    state=StepState.UNKNOWN,
                    event_id=event.event_id,
                    confidence=event.confidence,
                )
                return

            mismatch = self._step_mismatch(step, event)
            if mismatch is None:
                state.steps[step.code] = StepResult(
                    code=step.code,
                    state=StepState.COMPLETED,
                    event_id=event.event_id,
                    confidence=event.confidence,
                )
                return

            rule = self._matching_rule(step, event)
            if rule is not None:
                state.steps[step.code] = StepResult(
                    code=step.code,
                    state=StepState.VIOLATED,
                    event_id=event.event_id,
                    confidence=event.confidence,
                )
                state.violations.append(self._violation_from(rule, event, step, mismatch))
                return

    def _step_mismatch(self, step: StepDefinition, event: ActionEvent) -> str | None:
        actual_object = event.object.class_name if event.object else None
        checks = (
            ("object_class", step.object_class, actual_object),
            ("source_zone", step.source_zone, event.source_zone),
            ("target_zone", step.target_zone, event.target_zone),
        )
        for field, expected, actual in checks:
            if expected is not None and expected != actual:
                return field
        return None

    def _matching_rule(self, step: StepDefinition, event: ActionEvent) -> RuleDefinition | None:
        actual_object = event.object.class_name if event.object else None
        for rule in self._rules_by_action.get(event.action.value, []):
            if rule.step != step.code:
                continue
            mismatched = (
                (rule.object_class is not None and actual_object != rule.object_class)
                or (rule.source_zone is not None and event.source_zone != rule.source_zone)
                or (rule.target_zone is not None and event.target_zone != rule.target_zone)
            )
            if mismatched:
                return rule
        return None

    def _violation_from(
        self,
        rule: RuleDefinition,
        event: ActionEvent,
        step: StepDefinition,
        mismatch: str,
    ) -> Violation:
        actual_object = event.object.class_name if event.object else None
        expected = {
            "object_class": step.object_class,
            "source_zone": step.source_zone,
            "target_zone": step.target_zone,
        }
        actual = {
            "object_class": actual_object,
            "source_zone": event.source_zone,
            "target_zone": event.target_zone,
            "mismatch": mismatch,
        }
        return Violation(
            rule_id=rule.id,
            step=step.code,
            type=rule.violation.type,
            severity=rule.violation.severity,
            message=rule.violation.message,
            event_id=event.event_id,
            confidence=event.confidence,
            expected={key: value for key, value in expected.items() if value is not None},
            actual=actual,
        )

    def _refresh_ready_steps(self, state: _SessionState) -> None:
        completed = {
            code
            for code, result in state.steps.items()
            if result.state == StepState.COMPLETED
        }
        for step in self.rule_set.steps:
            current = state.steps[step.code]
            if current.state != StepState.PENDING:
                continue
            if all(predecessor in completed for predecessor in step.predecessors):
                state.steps[step.code] = StepResult(code=step.code, state=StepState.READY)

    def _finalize_missing_required_steps(self, state: _SessionState) -> None:
        for step in self.rule_set.steps:
            result = state.steps[step.code]
            if not step.required:
                continue
            if result.state in {StepState.COMPLETED, StepState.VIOLATED, StepState.UNKNOWN}:
                continue
            state.steps[step.code] = StepResult(code=step.code, state=StepState.VIOLATED)
            state.violations.append(
                Violation(
                    rule_id=f"AUTO-MISSING-{step.code}",
                    step=step.code,
                    type="MISSING",
                    severity="MAJOR",
                    message=f"required step {step.code} was not completed",
                    event_id="session-finalize",
                    confidence=1.0,
                    expected={"action": step.action.value},
                    actual={},
                )
            )

    @staticmethod
    def _score(violations: list[Violation]) -> float:
        penalties = {"INFO": 0.0, "MINOR": 2.0, "MAJOR": 10.0, "CRITICAL": 100.0}
        value = 100.0 - sum(penalties[item.severity.value] for item in violations)
        return max(0.0, value)
