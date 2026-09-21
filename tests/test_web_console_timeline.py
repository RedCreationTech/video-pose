from video_pose.web_console_assets import APP_JS, INDEX_HTML


def test_console_loads_immutable_session_timeline() -> None:
    assert "Session Timeline" in INDEX_HTML
    assert "/timeline" in APP_JS
    assert "loadSessionTimeline" in APP_JS
    assert "renderSessionTimeline" in APP_JS
    assert "RECOVERY" in APP_JS
