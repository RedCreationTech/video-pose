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
    order_violation_steps: set[str]


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
                    state=StepState.READY
                    if not step.predecessors
                    else StepState.PENDING,
                )
                for step in self.rule_set.steps
            },
            violations=[],
            order_violation_steps=set(),
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
        passed = not any(
            violation.severity.value in {"MAJOR", "CRITICAL"}
            for violation in state.violations
        )
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
            self._record_out_of_order(state, event)
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
            if mismatch is not None:
                rule = self._matching_rule(step, event)
                if rule is not None:
                    state.steps[step.code] = StepResult(
                        code=step.code,
                        state=StepState.VIOLATED,
                        event_id=event.event_id,
                        confidence=event.confidence,
                    )
                    state.violations.append(
                        self._violation_from(rule, event, step, mismatch)
                    )
                    return
                continue

            state.steps[step.code] = StepResult(
                code=step.code,
                state=StepState.COMPLETED,
                event_id=event.event_id,
                confidence=event.confidence,
            )
            temporal = self._temporal_violation(step, event)
            if temporal is not None:
                state.violations.append(temporal)
            return

    def _record_out_of_order(
        self,
        state: _SessionState,
        event: ActionEvent,
    ) -> None:
        completed = {
            code
            for code, result in state.steps.items()
            if result.state == StepState.COMPLETED
        }
        for step in self.rule_set.steps:
            if step.action != event.action:
                continue
            if state.steps[step.code].state != StepState.PENDING:
                continue
            if event.confidence < step.min_confidence:
                continue
            if self._step_mismatch(step, event) is not None:
                continue
            if step.code in state.order_violation_steps:
                return

            missing_predecessors = [
                predecessor
                for predecessor in step.predecessors
                if predecessor not in completed
            ]
            if not missing_predecessors:
                continue

            state.order_violation_steps.add(step.code)
            state.violations.append(
                Violation(
                    rule_id=f"AUTO-ORDER-{step.code}",
                    step=step.code,
                    type="ORDER",
                    severity="MAJOR",
                    message=(
                        f"step {step.code} occurred before required predecessors"
                    ),
                    event_id=event.event_id,
                    confidence=event.confidence,
                    expected={
                        "completed_predecessors": step.predecessors,
                    },
                    actual={
                        "completed_steps": sorted(completed),
                        "missing_predecessors": missing_predecessors,
                    },
                )
            )
            return

    def _temporal_violation(
        self,
        step: StepDefinition,
        event: ActionEvent,
    ) -> Violation | None:
        if step.min_duration_ms is None and step.max_duration_ms is None:
            return None

        duration_ms = (
            event.ended_at_ms - event.started_at_ms
            if event.ended_at_ms is not None
            else None
        )
        reason: str | None = None
        if duration_ms is None:
            reason = "duration_unavailable"
        elif (
            step.min_duration_ms is not None
            and duration_ms < step.min_duration_ms
        ):
            reason = "too_short"
        elif (
            step.max_duration_ms is not None
            and duration_ms > step.max_duration_ms
        ):
            reason = "too_long"

        if reason is None:
            return None

        return Violation(
            rule_id=f"AUTO-TEMPORAL-{step.code}",
            step=step.code,
            type="TEMPORAL",
            severity=step.temporal_severity,
            message=f"step {step.code} duration is outside configured range",
            event_id=event.event_id,
            confidence=event.confidence,
            expected={
                "min_duration_ms": step.min_duration_ms,
                "max_duration_ms": step.max_duration_ms,
            },
            actual={
                "duration_ms": duration_ms,
                "reason": reason,
            },
        )

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

    def _matching_rule(
        self,
        step: StepDefinition,
        event: ActionEvent,
    ) -> RuleDefinition | None:
        actual_object = event.object.class_name if event.object else None
        for rule in self._rules_by_action.get(event.action.value, []):
            if rule.step != step.code:
                continue
            mismatched = (
                (
                    rule.object_class is not None
                    and actual_object != rule.object_class
                )
                or (
                    rule.source_zone is not None
                    and event.source_zone != rule.source_zone
                )
                or (
                    rule.target_zone is not None
                    and event.target_zone != rule.target_zone
                )
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
            expected={
                key: value
                for key, value in expected.items()
                if value is not None
            },
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
                state.steps[step.code] = StepResult(
                    code=step.code,
                    state=StepState.READY,
                )

    def _finalize_missing_required_steps(self, state: _SessionState) -> None:
        for step in self.rule_set.steps:
            result = state.steps[step.code]
            if not step.required:
                continue
            if result.state in {
                StepState.COMPLETED,
                StepState.VIOLATED,
                StepState.UNKNOWN,
            }:
                continue
            state.steps[step.code] = StepResult(
                code=step.code,
                state=StepState.VIOLATED,
            )
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
        penalties = {
            "INFO": 0.0,
            "MINOR": 2.0,
            "MAJOR": 10.0,
            "CRITICAL": 100.0,
        }
        value = 100.0 - sum(
            penalties[item.severity.value] for item in violations
        )
        return max(0.0, value)
