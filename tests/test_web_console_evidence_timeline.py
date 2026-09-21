from video_pose.web_console_assets import APP_JS, STYLE_CSS


def test_console_has_multiview_evidence_timeline() -> None:
    assert 'slider.type = "range"' in APP_JS
    assert "closestEvidenceImages" in APP_JS
    assert "normalized_start_ms" in APP_JS
    assert "normalized_end_ms" in APP_JS
    assert "evidenceRenderVersions" in APP_JS
    assert ".evidence-timeline" in STYLE_CSS


def test_timeline_evidence_images_remain_authenticated() -> None:
    assert "fetchEvidenceImage" in APP_JS
    assert "headers: authHeaders(false)" in APP_JS
    assert "URL.createObjectURL" in APP_JS
    assert "access_token=" not in APP_JS
