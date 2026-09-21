import io
import json
import logging

from video_pose.structured_log import (
    configure_logging,
    log_event,
    sanitized_fields,
)


def test_structured_log_redacts_sensitive_fields_recursively() -> None:
    fields = sanitized_fields(
        {
            "camera_id": "front",
            "token": "secret-token",
            "nested": {
                "password": "p@ss",
                "uri": "rtsp://user:pass@camera/stream",
            },
            "message": "Bearer abc123",
        }
    )
    assert fields["camera_id"] == "front"
    assert fields["token"] == "[REDACTED]"
    assert fields["nested"]["password"] == "[REDACTED]"
    assert fields["nested"]["uri"] == "[REDACTED]"
    assert fields["message"] == "[REDACTED]"


def test_json_event_log_contains_correlation_fields() -> None:
    stream = io.StringIO()
    configure_logging(
        log_format="json",
        level="INFO",
        stream=stream,
    )
    logger = logging.getLogger("video_pose.test")
    log_event(
        logger,
        "quality_violation",
        session_id="s1",
        camera_id="front",
        rule_id="SYSTEM-QUALITY-CAMERA-FRONT",
    )
    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "quality_violation"
    assert payload["session_id"] == "s1"
    assert payload["camera_id"] == "front"
    assert payload["rule_id"] == "SYSTEM-QUALITY-CAMERA-FRONT"
    assert payload["level"] == "INFO"
