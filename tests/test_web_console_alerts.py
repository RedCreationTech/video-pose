from video_pose.web_console_assets import APP_JS, INDEX_HTML


def test_console_separates_readiness_blockers_and_quality_incidents() -> None:
    assert "现场告警" in INDEX_HTML
    assert "START BLOCKER" in APP_JS
    assert "QUALITY INCIDENT" in APP_JS
    assert "state.readinessFailures" in APP_JS
    assert "state.qualityIncidents" in APP_JS
    assert "SYSTEM_QUALITY" in APP_JS


def test_clear_alerts_only_clears_local_incidents() -> None:
    assert "function clearLocalAlerts" in APP_JS
    assert "state.qualityIncidents = []" in APP_JS
    assert "state.readinessFailures = []" not in APP_JS[
        APP_JS.index("function clearLocalAlerts"):
    ]
