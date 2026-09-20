from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionType(str, Enum):
    REACH = "REACH"
    GRASP = "GRASP"
    RELEASE = "RELEASE"
    PICK = "PICK"
    PLACE = "PLACE"
    MOVE = "MOVE"
    INSERT = "INSERT"
    REMOVE = "REMOVE"
    ROTATE = "ROTATE"
    OPERATE_TOOL = "OPERATE_TOOL"
    INSPECT = "INSPECT"
    ENTER_ZONE = "ENTER_ZONE"
    LEAVE_ZONE = "LEAVE_ZONE"
    CONFIRM = "CONFIRM"
    WAIT = "WAIT"


class StepState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class Severity(str, Enum):
    INFO = "INFO"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class Decision(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class ActionObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    class_name: str | None = Field(default=None, alias="class")


class ActionEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    event_id: str
    session_id: str
    sequence: int = Field(ge=0)
    action: ActionType
    actor_id: str = "operator-001"
    hand: str | None = None
    object: ActionObject | None = None
    source_zone: str | None = None
    target_zone: str | None = None
    started_at_ms: int = Field(ge=0)
    ended_at_ms: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    model_version: str = "replay-fixture"

    @model_validator(mode="after")
    def end_not_before_start(self) -> ActionEvent:
        if self.ended_at_ms is not None and self.ended_at_ms < self.started_at_ms:
            raise ValueError("ended_at_ms must be >= started_at_ms")
        return self


class StepDefinition(BaseModel):
    code: str
    name: str
    action: ActionType
    object_class: str | None = None
    source_zone: str | None = None
    target_zone: str | None = None
    predecessors: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    required: bool = True


class ViolationDefinition(BaseModel):
    type: str
    severity: Severity = Severity.MAJOR
    message: str


class RuleDefinition(BaseModel):
    id: str
    step: str
    action: ActionType
    object_class: str | None = None
    source_zone: str | None = None
    target_zone: str | None = None
    violation: ViolationDefinition


class RuleSet(BaseModel):
    operation: str
    version: int = Field(ge=1)
    steps: list[StepDefinition]
    rules: list[RuleDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> RuleSet:
        step_codes = [step.code for step in self.steps]
        if len(step_codes) != len(set(step_codes)):
            raise ValueError("duplicate step code")
        known = set(step_codes)
        for step in self.steps:
            missing = set(step.predecessors) - known
            if missing:
                detail = sorted(missing)
                raise ValueError(
                    f"step {step.code} references missing predecessors: {detail}"
                )
        for rule in self.rules:
            if rule.step not in known:
                raise ValueError(f"rule {rule.id} references missing step: {rule.step}")
        return self


class StepResult(BaseModel):
    code: str
    state: StepState
    event_id: str | None = None
    confidence: float | None = None


class Violation(BaseModel):
    rule_id: str
    step: str
    type: str
    severity: Severity
    message: str
    event_id: str
    confidence: float
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)


class ReplayResult(BaseModel):
    session_id: str
    operation: str
    rule_set_version: int
    steps: list[StepResult]
    violations: list[Violation]
    score: float
    passed: bool
