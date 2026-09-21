from __future__ import annotations

import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel

_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})$"
)

_trace_id_var: ContextVar[str | None] = ContextVar(
    "video_pose_trace_id",
    default=None,
)
_span_id_var: ContextVar[str | None] = ContextVar(
    "video_pose_span_id",
    default=None,
)
_trace_flags_var: ContextVar[str] = ContextVar(
    "video_pose_trace_flags",
    default="01",
)


class TraceContext(BaseModel):
    trace_id: str
    span_id: str
    flags: str = "01"


def parse_traceparent(value: str | None) -> TraceContext | None:
    if not value:
        return None
    match = _TRACEPARENT.fullmatch(value.strip().lower())
    if match is None:
        return None
    trace_id = match.group("trace_id")
    span_id = match.group("span_id")
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
        flags=match.group("flags"),
    )


def new_trace_context(
    parent: TraceContext | None = None,
    *,
    trace_id: str | None = None,
) -> TraceContext:
    resolved_trace_id = (
        trace_id
        or (parent.trace_id if parent is not None else None)
        or secrets.token_hex(16)
    )
    flags = parent.flags if parent is not None else "01"
    return TraceContext(
        trace_id=resolved_trace_id,
        span_id=secrets.token_hex(8),
        flags=flags,
    )


def format_traceparent(context: TraceContext) -> str:
    return (
        f"00-{context.trace_id}-"
        f"{context.span_id}-{context.flags}"
    )


def activate_trace_context(context: TraceContext) -> None:
    _trace_id_var.set(context.trace_id)
    _span_id_var.set(context.span_id)
    _trace_flags_var.set(context.flags)


@contextmanager
def use_trace_context(
    context: TraceContext,
) -> Iterator[TraceContext]:
    trace_token = _trace_id_var.set(context.trace_id)
    span_token = _span_id_var.set(context.span_id)
    flags_token = _trace_flags_var.set(context.flags)
    try:
        yield context
    finally:
        _trace_id_var.reset(trace_token)
        _span_id_var.reset(span_token)
        _trace_flags_var.reset(flags_token)


def current_trace_id() -> str | None:
    return _trace_id_var.get()


def current_trace_fields() -> dict[str, str]:
    trace_id = _trace_id_var.get()
    span_id = _span_id_var.get()
    if trace_id is None or span_id is None:
        return {}
    return {
        "trace_id": trace_id,
        "span_id": span_id,
    }
