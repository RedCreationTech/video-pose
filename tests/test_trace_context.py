from video_pose.trace_context import (
    current_trace_fields,
    format_traceparent,
    new_trace_context,
    parse_traceparent,
    use_trace_context,
)


def test_traceparent_round_trip_and_child_span() -> None:
    incoming = (
        "00-0123456789abcdef0123456789abcdef-"
        "0123456789abcdef-01"
    )
    parent = parse_traceparent(incoming)
    assert parent is not None
    child = new_trace_context(parent)
    assert child.trace_id == parent.trace_id
    assert child.span_id != parent.span_id
    assert format_traceparent(child).startswith(
        "00-0123456789abcdef0123456789abcdef-"
    )


def test_invalid_or_zero_traceparent_is_rejected() -> None:
    assert parse_traceparent("invalid") is None
    assert parse_traceparent(
        "00-" + "0" * 32 + "-" + "1" * 16 + "-01"
    ) is None


def test_trace_context_is_scoped() -> None:
    context = new_trace_context()
    assert current_trace_fields() == {}
    with use_trace_context(context):
        fields = current_trace_fields()
        assert fields["trace_id"] == context.trace_id
        assert fields["span_id"] == context.span_id
    assert current_trace_fields() == {}
