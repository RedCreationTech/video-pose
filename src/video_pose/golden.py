from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ExpectedAction(BaseModel):
    action: str
    object_class: str | None = None


class ExpectedViolation(BaseModel):
    type: str
    step: str | None = None


class GoldenGroundTruth(BaseModel):
    session_id: str
    expected_pass: bool
    actions: list[ExpectedAction] = Field(default_factory=list)
    violations: list[ExpectedViolation] = Field(default_factory=list)


class GoldenSession(BaseModel):
    session_id: str
    ground_truth: str
    result: str


class GoldenDataset(BaseModel):
    name: str
    version: str
    sessions: list[GoldenSession]


class MetricSummary(BaseModel):
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


class GoldenEvaluationReport(BaseModel):
    dataset: str
    version: str
    session_count: int
    session_pass_accuracy: float
    actions: MetricSummary
    violations: MetricSummary


def _metric(expected: Counter[tuple[str, str]], actual: Counter[tuple[str, str]]) -> MetricSummary:
    keys = set(expected) | set(actual)
    true_positive = sum(min(expected[key], actual[key]) for key in keys)
    false_positive = sum(max(0, actual[key] - expected[key]) for key in keys)
    false_negative = sum(max(0, expected[key] - actual[key]) for key in keys)
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = (
        true_positive / precision_denominator if precision_denominator else 1.0
    )
    recall = true_positive / recall_denominator if recall_denominator else 1.0
    denominator = precision + recall
    f1 = 2.0 * precision * recall / denominator if denominator else 0.0
    return MetricSummary(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _action_key(payload: dict[str, object]) -> tuple[str, str]:
    action = str(payload.get("action", ""))
    object_payload = payload.get("object")
    object_class = ""
    if isinstance(object_payload, dict):
        object_class = str(object_payload.get("class", ""))
    return action, object_class


def _violation_key(payload: dict[str, object]) -> tuple[str, str]:
    return str(payload.get("type", "")), str(payload.get("step", ""))


def evaluate_golden_dataset(path: str | Path) -> GoldenEvaluationReport:
    manifest_path = Path(path).resolve()
    dataset = GoldenDataset.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )
    expected_actions: Counter[tuple[str, str]] = Counter()
    actual_actions: Counter[tuple[str, str]] = Counter()
    expected_violations: Counter[tuple[str, str]] = Counter()
    actual_violations: Counter[tuple[str, str]] = Counter()
    pass_matches = 0

    for session in dataset.sessions:
        ground_truth_path = manifest_path.parent / session.ground_truth
        result_path = manifest_path.parent / session.result
        truth = GoldenGroundTruth.model_validate(
            yaml.safe_load(ground_truth_path.read_text(encoding="utf-8"))
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))

        for action in truth.actions:
            expected_actions[(action.action, action.object_class or "")] += 1
        for payload in result.get("actions", []):
            if isinstance(payload, dict):
                actual_actions[_action_key(payload)] += 1

        for violation in truth.violations:
            expected_violations[(violation.type, violation.step or "")] += 1
        evaluation = result.get("evaluation")
        actual_pass = False
        if isinstance(evaluation, dict):
            actual_pass = bool(evaluation.get("passed", False))
            for payload in evaluation.get("violations", []):
                if isinstance(payload, dict):
                    actual_violations[_violation_key(payload)] += 1
        if actual_pass == truth.expected_pass:
            pass_matches += 1

    session_count = len(dataset.sessions)
    accuracy = pass_matches / session_count if session_count else 1.0
    return GoldenEvaluationReport(
        dataset=dataset.name,
        version=dataset.version,
        session_count=session_count,
        session_pass_accuracy=accuracy,
        actions=_metric(expected_actions, actual_actions),
        violations=_metric(expected_violations, actual_violations),
    )
