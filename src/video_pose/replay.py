from __future__ import annotations

import json
from pathlib import Path

from .contracts import ActionEvent, ReplayResult
from .rules import RuleEngine


def load_events(path: str | Path) -> list[ActionEvent]:
    events: list[ActionEvent] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                payload = json.loads(stripped)
                events.append(ActionEvent.model_validate(payload))
            except Exception as exc:  # pragma: no cover - message path
                raise ValueError(
                    f"invalid replay event at line {line_number}: {exc}"
                ) from exc
    return events


def run_replay(
    events_path: str | Path,
    rules_path: str | Path,
    *,
    session_end_ms: int | None = None,
) -> ReplayResult:
    engine = RuleEngine.from_yaml(rules_path)
    return engine.evaluate(
        load_events(events_path),
        session_end_ms=session_end_ms,
    )
