from __future__ import annotations

from pydantic import BaseModel, Field

from .contracts import ActionEvent, ReplayResult, StepResult, Violation
from .rules import RuleEngine


class RuleSessionUpdate(BaseModel):
    result: ReplayResult
    new_violations: list[Violation] = Field(default_factory=list)
    changed_steps: list[StepResult] = Field(default_factory=list)


class RealtimeRuleSession:
    """Realtime facade over the deterministic replay rule engine."""

    def __init__(
        self,
        engine: RuleEngine,
        *,
        session_id: str,
    ) -> None:
        self.engine = engine
        self.session_id = session_id
        self._events: list[ActionEvent] = []
        self._event_ids: set[str] = set()
        self._sequences: set[int] = set()
        self._last_result: ReplayResult | None = None

    def ingest(self, event: ActionEvent) -> RuleSessionUpdate:
        if event.session_id != self.session_id:
            raise ValueError("event belongs to another realtime rule session")
        if (
            event.event_id not in self._event_ids
            and event.sequence not in self._sequences
        ):
            self._events.append(event)
            self._event_ids.add(event.event_id)
            self._sequences.add(event.sequence)

        now_ms = event.ended_at_ms or event.started_at_ms
        return self._evaluate(now_ms=now_ms, finalize=False)

    def tick(self, now_ms: int) -> RuleSessionUpdate:
        return self._evaluate(now_ms=now_ms, finalize=False)

    def finish(self, session_end_ms: int) -> RuleSessionUpdate:
        return self._evaluate(now_ms=session_end_ms, finalize=True)

    def current_result(self) -> ReplayResult | None:
        return (
            self._last_result.model_copy(deep=True)
            if self._last_result is not None
            else None
        )

    def _evaluate(
        self,
        *,
        now_ms: int,
        finalize: bool,
    ) -> RuleSessionUpdate:
        result = self.engine.evaluate(
            self._events,
            session_end_ms=now_ms,
            finalize=finalize,
            session_id=self.session_id,
        )
        update = RuleSessionUpdate(
            result=result,
            new_violations=self._new_violations(result),
            changed_steps=self._changed_steps(result),
        )
        self._last_result = result
        return update

    def _new_violations(
        self,
        result: ReplayResult,
    ) -> list[Violation]:
        previous = {
            (item.rule_id, item.step, item.type)
            for item in (
                self._last_result.violations
                if self._last_result is not None
                else []
            )
        }
        return [
            item
            for item in result.violations
            if (item.rule_id, item.step, item.type) not in previous
        ]

    def _changed_steps(
        self,
        result: ReplayResult,
    ) -> list[StepResult]:
        if self._last_result is None:
            return result.steps
        previous = {
            item.code: (item.state, item.event_id)
            for item in self._last_result.steps
        }
        return [
            item
            for item in result.steps
            if previous.get(item.code) != (item.state, item.event_id)
        ]
