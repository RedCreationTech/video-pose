from video_pose.web_console_assets import APP_JS


def test_console_uses_short_lived_realtime_ticket() -> None:
    assert "/api/v1/auth/realtime-ticket" in APP_JS
    assert "/api/v1/realtime?ticket=" in APP_JS
    assert "access_token=" not in APP_JS
    assert "state.realtimeRetry" in APP_JS
