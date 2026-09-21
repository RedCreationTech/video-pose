import builtins

from video_pose.telemetry import (
    configure_telemetry_from_environment,
    telemetry_span,
)
from video_pose.trace_context import (
    new_trace_context,
    use_trace_context,
)


def test_telemetry_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_POSE_OTEL_ENABLED", "0")
    state = configure_telemetry_from_environment()
    assert state.enabled is False
    assert state.configured is False
    with telemetry_span("disabled-span") as span:
        assert span is None


def test_telemetry_missing_optional_dependency_never_breaks_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIDEO_POSE_OTEL_ENABLED", "1")
    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("simulated missing OpenTelemetry")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(
        builtins,
        "__import__",
        failing_import,
    )
    state = configure_telemetry_from_environment()
    assert state.enabled is True
    assert state.configured is False
    assert state.error_type == "ImportError"

    context = new_trace_context()
    with use_trace_context(context):
        with telemetry_span("no-sdk") as span:
            assert span is None
