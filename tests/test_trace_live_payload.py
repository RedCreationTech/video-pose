from video_pose.contracts import ReplayResult
from video_pose.live_payload import live_update_payload
from video_pose.realtime_rules import RuleSessionUpdate
from video_pose.session_quality import SessionQualityUpdate
from video_pose.trace_context import (
    new_trace_context,
    use_trace_context,
)


def test_live_payload_carries_current_trace_context() -> None:
    result = ReplayResult(
        session_id="s1",
        operation="demo",
        rule_set_version=1,
        steps=[],
        violations=[],
        score=100,
        passed=True,
    )
    context = new_trace_context()
    with use_trace_context(context):
        payload = live_update_payload(
            SessionQualityUpdate(
                timestamp_ms=10,
                rule_update=RuleSessionUpdate(
                    result=result
                ),
            )
        )
    assert payload["trace_id"] == context.trace_id
    assert payload["span_id"] == context.span_id
