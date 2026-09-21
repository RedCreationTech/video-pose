from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from .structured_log import log_event
from .trace_context import TraceContext, current_trace_fields

LOGGER = logging.getLogger("video_pose.telemetry")


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _primitive_attributes(
    attributes: dict[str, Any] | None,
) -> dict[str, str | int | float | bool]:
    if not attributes:
        return {}
    output: dict[str, str | int | float | bool] = {}
    for key, value in attributes.items():
        if isinstance(value, (str, int, float, bool)):
            output[key] = value
        elif value is not None:
            output[key] = str(value)
    return output


@dataclass(slots=True)
class TelemetryState:
    enabled: bool = False
    configured: bool = False
    service_name: str = "video-pose-edge"
    endpoint_configured: bool = False
    error_type: str | None = None
    provider: Any | None = None
    tracer: Any | None = None


_STATE = TelemetryState()


def telemetry_state() -> TelemetryState:
    return TelemetryState(
        enabled=_STATE.enabled,
        configured=_STATE.configured,
        service_name=_STATE.service_name,
        endpoint_configured=_STATE.endpoint_configured,
        error_type=_STATE.error_type,
        provider=_STATE.provider,
        tracer=_STATE.tracer,
    )


def configure_telemetry_from_environment() -> TelemetryState:
    enabled = _parse_bool(
        os.getenv("VIDEO_POSE_OTEL_ENABLED"),
        False,
    )
    service_name = os.getenv(
        "OTEL_SERVICE_NAME",
        "video-pose-edge",
    )
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or None
    )

    if not enabled:
        _set_state(
            TelemetryState(
                enabled=False,
                configured=False,
                service_name=service_name,
                endpoint_configured=bool(endpoint),
            )
        )
        return telemetry_state()

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import (
            SERVICE_NAME,
            Resource,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                SERVICE_NAME: service_name,
                "service.version": os.getenv(
                    "VIDEO_POSE_VERSION",
                    "unknown",
                ),
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = (
            OTLPSpanExporter(endpoint=endpoint)
            if endpoint
            else OTLPSpanExporter()
        )
        provider.add_span_processor(
            BatchSpanProcessor(exporter)
        )
        tracer = provider.get_tracer("video_pose")

        _set_state(
            TelemetryState(
                enabled=True,
                configured=True,
                service_name=service_name,
                endpoint_configured=bool(endpoint),
                provider=provider,
                tracer=tracer,
            )
        )
        log_event(
            LOGGER,
            "otel_configured",
            service_name=service_name,
            endpoint_configured=bool(endpoint),
        )
    except Exception as exc:
        _set_state(
            TelemetryState(
                enabled=True,
                configured=False,
                service_name=service_name,
                endpoint_configured=bool(endpoint),
                error_type=type(exc).__name__,
            )
        )
        log_event(
            LOGGER,
            "otel_configuration_failed",
            level=logging.WARNING,
            error_type=type(exc).__name__,
            endpoint_configured=bool(endpoint),
        )

    return telemetry_state()


def _set_state(state: TelemetryState) -> None:
    global _STATE
    old = _STATE
    if (
        old.provider is not None
        and old.provider is not state.provider
    ):
        try:
            old.provider.shutdown()
        except Exception:
            pass
    _STATE = state


def shutdown_telemetry() -> None:
    provider = _STATE.provider
    if provider is not None:
        try:
            provider.shutdown()
        except Exception as exc:
            log_event(
                LOGGER,
                "otel_shutdown_failed",
                level=logging.WARNING,
                error_type=type(exc).__name__,
            )


def _current_parent_context() -> TraceContext | None:
    fields = current_trace_fields()
    trace_id = fields.get("trace_id")
    span_id = fields.get("span_id")
    if not trace_id or not span_id:
        return None
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
    )


def _otel_parent_context(
    trace_context: TraceContext,
) -> Any:
    from opentelemetry import trace
    from opentelemetry.trace import (
        NonRecordingSpan,
        SpanContext,
        TraceFlags,
        TraceState,
    )

    span_context = SpanContext(
        trace_id=int(trace_context.trace_id, 16),
        span_id=int(trace_context.span_id, 16),
        is_remote=False,
        trace_flags=(
            TraceFlags.SAMPLED
            if trace_context.flags == "01"
            else TraceFlags.DEFAULT
        ),
        trace_state=TraceState(),
    )
    return trace.set_span_in_context(
        NonRecordingSpan(span_context)
    )


@contextmanager
def telemetry_span(
    name: str,
    *,
    trace_context: TraceContext | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    tracer = _STATE.tracer
    if not _STATE.configured or tracer is None:
        yield None
        return

    parent = trace_context or _current_parent_context()
    context = (
        _otel_parent_context(parent)
        if parent is not None
        else None
    )
    try:
        span = tracer.start_span(
            name,
            context=context,
            attributes=_primitive_attributes(attributes),
        )
    except Exception as exc:
        log_event(
            LOGGER,
            "otel_span_start_failed",
            level=logging.WARNING,
            span_name=name,
            error_type=type(exc).__name__,
        )
        yield None
        return

    try:
        yield span
    finally:
        try:
            span.end()
        except Exception as exc:
            log_event(
                LOGGER,
                "otel_span_end_failed",
                level=logging.WARNING,
                span_name=name,
                error_type=type(exc).__name__,
            )


def emit_telemetry_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> None:
    with telemetry_span(
        name,
        attributes=attributes,
    ):
        pass
