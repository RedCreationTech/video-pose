from video_pose.web_console_assets import APP_JS, INDEX_HTML


def test_console_contains_history_evidence_and_recovery_workflow() -> None:
    assert "Session 历史" in INDEX_HTML
    assert "Evidence Explorer" in INDEX_HTML
    assert "Crash Recovery" in INDEX_HTML
    assert "/api/v1/sessions?limit=30" in APP_JS
    assert "/evidence" in APP_JS
    assert "/api/v1/runtime/persistence/incomplete-sessions" in APP_JS
    assert "SYSTEM-QUALITY-RECOVERY" in APP_JS


def test_evidence_preview_uses_auth_fetch_not_token_url() -> None:
    assert "headers: authHeaders(false)" in APP_JS
    assert "URL.createObjectURL" in APP_JS
    assert "URL.revokeObjectURL" in APP_JS
    assert "access_token=" not in APP_JS
