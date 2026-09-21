from video_pose.web_console_assets import APP_JS, STYLE_CSS


def test_timeline_events_can_focus_related_evidence() -> None:
    assert "focusTimelineEvidence" in APP_JS
    assert "findEvidenceForTimelineEvent" in APP_JS
    assert "evidenceCenterPercentage" in APP_JS
    assert "scheduled_timestamp_ms" in APP_JS
    assert "CSS.escape" in APP_JS
    assert ".evidence-card.focused" in STYLE_CSS


def test_timeline_evidence_matching_uses_stable_identity() -> None:
    assert "data.evidence_id" in APP_JS
    assert "data.rule_id" in APP_JS
    assert "data.event_id" in APP_JS
