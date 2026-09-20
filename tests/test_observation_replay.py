from pathlib import Path

from video_pose.observation_replay import (
    load_observations,
    observations_to_actions,
    run_observation_replay,
)

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "fixtures/rules/pick-place.yaml"


def test_observations_generate_pick_and_place() -> None:
    path = ROOT / "fixtures/observations/pick-place-compliant.jsonl"
    actions = observations_to_actions(load_observations(path))
    assert [action.action.value for action in actions] == ["PICK", "PLACE"]
    assert actions[0].source_zone == "component_bin_A"
    assert actions[1].target_zone == "assembly_zone"


def test_observation_replay_passes_compliant_flow() -> None:
    path = ROOT / "fixtures/observations/pick-place-compliant.jsonl"
    result = run_observation_replay(path, RULES)
    assert result.passed is True
    assert result.score == 100.0
    assert result.violations == []


def test_observation_replay_detects_wrong_zone() -> None:
    path = ROOT / "fixtures/observations/pick-place-wrong-zone.jsonl"
    result = run_observation_replay(path, RULES)
    assert result.passed is False
    assert any(item.type == "SPATIAL" for item in result.violations)
