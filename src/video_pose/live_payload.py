from __future__ import annotations

from typing import Any

from .live_runtime import LiveAnalysisUpdate
from .session_quality import SessionQualityUpdate


def _rule_update_payload(rule_update: Any) -> dict[str, Any]:
    return {
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


def live_update_payload(
    update: LiveAnalysisUpdate | SessionQualityUpdate,
) -> dict[str, Any]:
    if isinstance(update, SessionQualityUpdate):
        return {
            "timestamp_ms": update.timestamp_ms,
            "actions": [],
            "rule_updates": [
                _rule_update_payload(update.rule_update)
            ],
            "quality_update": True,
        }

    return {
        "timestamp_ms": update.trace.frame_set.reference_timestamp_ms,
        "actions": [
            action.model_dump(mode="json", by_alias=True)
            for action in update.trace.actions
        ],
        "rule_updates": [
            _rule_update_payload(rule_update)
            for rule_update in update.rule_updates
        ],
    }
