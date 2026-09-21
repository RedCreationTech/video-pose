from video_pose.web_console_assets import APP_JS, INDEX_HTML, STYLE_CSS


def test_console_can_export_and_print_preflight() -> None:
    assert "班前 Preflight Checklist" in INDEX_HTML
    assert "/api/v1/runtime/preflight" in APP_JS
    assert "function exportPreflight" in APP_JS
    assert "function printPreflight" in APP_JS
    assert "video-pose-preflight-" in APP_JS
    assert "body.print-preflight" in STYLE_CSS
