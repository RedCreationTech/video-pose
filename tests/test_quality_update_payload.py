from video_pose.contracts import ReplayResult, Violation
from video_pose.live_payload import live_update_payload
from video_pose.realtime_rules import RuleSessionUpdate
from video_pose.session_quality import SessionQualityUpdate


def test_quality_update_uses_existing_rule_update_payload_shape() -> None:
    violation = Violation(
        rule_id="SYSTEM-QUALITY-SYNC",
        step="SYSTEM",
        type="SYSTEM_QUALITY",
        severity="CRITICAL",
        message="sync stalled",
        event_id="quality-sync-1",
        confidence=1.0,
    )
    result = ReplayResult(
        session_id="s1",
        operation="demo",
        rule_set_version=1,
        steps=[],
        violations=[violation],
        score=0.0,
        passed=False,
    )
    payload = live_update_payload(
        SessionQualityUpdate(
            timestamp_ms=1234,
            rule_update=RuleSessionUpdate(
                result=result,
                new_violations=[violation],
            ),
        )
    )
    assert payload["timestamp_ms"] == 1234
    assert payload["actions"] == []
    assert payload["quality_update"] is True
    assert (
        payload["rule_updates"][0]["new_violations"][0]["type"]
        == "SYSTEM_QUALITY"
    )
