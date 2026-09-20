from pathlib import Path

from video_pose.contracts import StepState
from video_pose.replay import run_replay

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "fixtures/rules/assembly-a.yaml"


def test_compliant_replay_passes() -> None:
    result = run_replay(ROOT / "fixtures/replay/compliant.jsonl", RULES)
    assert result.passed is True
    assert result.score == 100.0
    assert result.violations == []
    assert all(step.state == StepState.COMPLETED for step in result.steps)


def test_wrong_tool_is_explained_and_fails() -> None:
    result = run_replay(ROOT / "fixtures/replay/wrong-tool.jsonl", RULES)
    assert result.passed is False
    assert any(v.type == "WRONG_TOOL" and v.rule_id == "R-S030-TOOL-01" for v in result.violations)
    assert next(step for step in result.steps if step.code == "S030").state == StepState.VIOLATED


def test_duplicate_event_is_idempotent() -> None:
    from video_pose.contracts import ActionEvent
    from video_pose.replay import load_events
    from video_pose.rules import RuleEngine

    events = load_events(ROOT / "fixtures/replay/compliant.jsonl")
    duplicate = ActionEvent.model_validate(events[0].model_dump(mode="json", by_alias=True))
    result = RuleEngine.from_yaml(RULES).evaluate([events[0], duplicate, *events[1:]])
    assert result.passed is True
    assert result.score == 100.0
