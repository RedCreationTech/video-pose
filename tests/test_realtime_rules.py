from pathlib import Path

from video_pose.contracts import ActionEvent, ActionObject
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine

ROOT = Path(__file__).resolve().parents[1]


def test_realtime_session_reports_step_delta_on_ingest() -> None:
    engine = RuleEngine.from_yaml(
        ROOT / "fixtures/rules/pick-place.yaml"
    )
    session = RealtimeRuleSession(engine, session_id="rt-1")
    update = session.ingest(
        ActionEvent(
            event_id="pick",
            session_id="rt-1",
            sequence=1,
            action="PICK",
            object=ActionObject(id="part", **{"class": "component_A"}),
            source_zone="component_bin_A",
            started_at_ms=100,
            confidence=0.95,
        )
    )
    assert update.result.steps[0].state.value == "COMPLETED"
    assert any(step.code == "S010" for step in update.changed_steps)
    assert update.new_violations == []


def test_realtime_tick_can_timeout_before_any_action() -> None:
    engine = RuleEngine.from_yaml(
        ROOT / "fixtures/rules/realtime-root-timeout.yaml"
    )
    session = RealtimeRuleSession(engine, session_id="rt-timeout")
    update = session.tick(1001)
    assert [item.type for item in update.new_violations] == ["TIMEOUT"]
    assert update.result.steps[0].state.value == "VIOLATED"


def test_realtime_duplicate_event_does_not_create_new_delta() -> None:
    engine = RuleEngine.from_yaml(
        ROOT / "fixtures/rules/pick-place.yaml"
    )
    session = RealtimeRuleSession(engine, session_id="rt-dup")
    event = ActionEvent(
        event_id="pick",
        session_id="rt-dup",
        sequence=1,
        action="PICK",
        object=ActionObject(id="part", **{"class": "component_A"}),
        source_zone="component_bin_A",
        started_at_ms=100,
        confidence=0.95,
    )
    first = session.ingest(event)
    second = session.ingest(event)
    assert first.changed_steps
    assert second.changed_steps == []
    assert second.new_violations == []


def test_finish_adds_missing_without_affecting_realtime_history() -> None:
    engine = RuleEngine.from_yaml(
        ROOT / "fixtures/rules/pick-place.yaml"
    )
    session = RealtimeRuleSession(engine, session_id="rt-finish")
    session.ingest(
        ActionEvent(
            event_id="pick",
            session_id="rt-finish",
            sequence=1,
            action="PICK",
            object=ActionObject(id="part", **{"class": "component_A"}),
            source_zone="component_bin_A",
            started_at_ms=100,
            confidence=0.95,
        )
    )
    final = session.finish(2000)
    assert any(item.type == "MISSING" for item in final.new_violations)
    assert final.result.passed is False
