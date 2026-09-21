from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

from .trace_context import current_trace_fields

_SENSITIVE_FRAGMENTS = (
    "authorization",
    "cookie",
    "database_url",
    "password",
    "secret",
    "token",
    "uri",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(
        fragment in normalized
        for fragment in _SENSITIVE_FRAGMENTS
    )


def _sanitize(value: Any, *, key: str = "") -> Any:
    if key and _is_sensitive_key(key):
        return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(item_key): _sanitize(
                item_value,
                key=str(item_key),
            )
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _sanitize(item)
            for item in value
        ]

    if isinstance(value, str):
        lowered = value.lower()
        if lowered.startswith("bearer "):
            return "[REDACTED]"
        if "://" in value and "@" in value:
            return "[REDACTED_URI]"

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def sanitized_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _sanitize(value, key=key)
        for key, value in fields.items()
    }


class JsonEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = sanitized_fields(
            getattr(record, "event_fields", {})
        )
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(
                record,
                "event_name",
                record.getMessage(),
            ),
        }
        payload.update(fields)
        if record.exc_info:
            payload["exception_type"] = (
                record.exc_info[0].__name__
                if record.exc_info[0] is not None
                else "Exception"
            )
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


class TextEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = sanitized_fields(
            getattr(record, "event_fields", {})
        )
        suffix = " ".join(
            f"{key}={value}"
            for key, value in sorted(fields.items())
        )
        base = (
            f"{datetime.now(UTC).isoformat()} "
            f"{record.levelname} "
            f"{record.name} "
            f"{getattr(record, 'event_name', record.getMessage())}"
        )
        return f"{base} {suffix}".rstrip()


def configure_logging(
    *,
    log_format: str | None = None,
    level: str | int | None = None,
    stream: TextIO | None = None,
) -> None:
    resolved_format = (
        log_format
        or os.getenv("VIDEO_POSE_LOG_FORMAT", "json")
    ).lower()
    if resolved_format not in {"json", "text"}:
        raise ValueError(
            "VIDEO_POSE_LOG_FORMAT must be json or text"
        )

    resolved_level: str | int = (
        level
        or os.getenv("VIDEO_POSE_LOG_LEVEL", "INFO")
    )
    if isinstance(resolved_level, str):
        numeric_level = logging.getLevelNamesMapping().get(
            resolved_level.upper()
        )
        if numeric_level is None:
            raise ValueError(
                f"invalid log level: {resolved_level}"
            )
    else:
        numeric_level = resolved_level

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_video_pose_handler", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stdout)
    handler._video_pose_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(
        JsonEventFormatter()
        if resolved_format == "json"
        else TextEventFormatter()
    )
    root.addHandler(handler)
    root.setLevel(numeric_level)

    logging.getLogger("video_pose").setLevel(numeric_level)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    correlated = {
        **current_trace_fields(),
        **fields,
    }
    logger.log(
        level,
        event,
        extra={
            "event_name": event,
            "event_fields": sanitized_fields(correlated),
        },
    )
