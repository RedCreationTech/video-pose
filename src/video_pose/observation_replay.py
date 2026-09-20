from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .baseline_action import PickPlaceActionRecognizer
from .contracts import ActionEvent, ReplayResult
from .fusion import fuse_observations
from .observations import Observation
from .rules import RuleEngine


def load_observations(path: str | Path) -> list[Observation]:
    output: list[Observation] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                output.append(Observation.model_validate(json.loads(stripped)))
            except Exception as exc:
                raise ValueError(
                    f"invalid observation at line {line_number}: {exc}"
                ) from exc
    return output


def observations_to_actions(observations: list[Observation]) -> list[ActionEvent]:
    if not observations:
        raise ValueError("at least one observation is required")
    session_ids = {item.session_id for item in observations}
    if len(session_ids) != 1:
        raise ValueError("all observations must belong to one session")

    by_timestamp: dict[float, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_timestamp[observation.timestamp_ms].append(observation)

    session_id = next(iter(session_ids))
    recognizer = PickPlaceActionRecognizer(session_id=session_id)
    actions: list[ActionEvent] = []
    for timestamp in sorted(by_timestamp):
        fused = fuse_observations(by_timestamp[timestamp])
        actions.extend(recognizer.ingest(fused))
    return actions


def run_observation_replay(
    observations_path: str | Path,
    rules_path: str | Path,
) -> ReplayResult:
    observations = load_observations(observations_path)
    actions = observations_to_actions(observations)
    return RuleEngine.from_yaml(rules_path).evaluate(actions)
