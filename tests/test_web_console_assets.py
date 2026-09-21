from video_pose.web_console_assets import (
    APP_JS,
    INDEX_HTML,
    STYLE_CSS,
)


def test_console_assets_have_no_external_dependencies() -> None:
    combined = INDEX_HTML + STYLE_CSS + APP_JS
    assert "https://" not in combined
    assert "http://" not in combined
    assert '<script defer src="/console/app.js"></script>' in INDEX_HTML
    assert "/console/style.css" in INDEX_HTML


def test_console_avoids_dynamic_inner_html() -> None:
    assert "innerHTML" not in APP_JS
