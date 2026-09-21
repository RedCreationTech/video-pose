from pathlib import Path

from video_pose.contracts import Violation
from video_pose.realtime_rules import RealtimeRuleSession
from video_pose.rules import RuleEngine

ROOT = Path(__file__).resolve().parents[1]


def test_external_quality_violation_makes_session_fail() -> None:
    session = RealtimeRuleSession(
        RuleEngine.from_yaml(
            ROOT / "fixtures/rules/pick-place.yaml"
        ),
        session_id="quality-session",
    )
    violation = Violation(
        rule_id="SYSTEM-QUALITY-CAMERA-FRONT",
        step="SYSTEM",
        type="SYSTEM_QUALITY",
        severity="CRITICAL",
        message="front camera unavailable",
        event_id="quality-camera-front-1",
        confidence=1.0,
    )
    update = session.record_external_violation(
        violation,
        now_ms=1000,
    )
    assert update.result.passed is False
    assert update.result.score == 0.0
    assert [item.type for item in update.new_violations] == [
        "SYSTEM_QUALITY"
    ]

    duplicate = session.record_external_violation(
        violation,
        now_ms=1100,
    )
    assert duplicate.new_violations == []
    assert len(duplicate.result.violations) == 1
