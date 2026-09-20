from __future__ import annotations

from typing import Any

from .live_runtime import LiveAnalysisUpdate


def live_update_payload(update: LiveAnalysisUpdate) -> dict[str, Any]:
    return {
        "timestamp_ms": update.trace.frame_set.reference_timestamp_ms,
        "actions": [
            action.model_dump(mode="json", by_alias=True)
            for action in update.trace.actions
        ],
        "rule_updates": [
            {
                "new_violations": [
                    item.model_dump(mode="json")
                    for item in rule_update.new_violations
                ],
                "changed_steps": [
                    item.model_dump(mode="json")
                    for item in rule_update.changed_steps
                ],
                "score": rule_update.result.score,
                "passed": rule_update.result.passed,
            }
            for rule_update in update.rule_updates
        ],
    }
