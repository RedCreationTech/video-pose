from video_pose.gstreamer_capture import GStreamerCaptureOptions
from video_pose.native_gstreamer_capture import (
    NativeTimestampResolver,
    build_native_gstreamer_rtsp_pipeline,
)
from video_pose.runtime_config import CaptureTimestampSource


def test_native_pipeline_names_source_and_sink() -> None:
    pipeline = build_native_gstreamer_rtsp_pipeline(
        "rtsp://camera/stream",
        codec="h264",
        options=GStreamerCaptureOptions(
            latency_ms=120,
            max_buffers=1,
        ),
        rfc7273_sync=True,
        add_reference_timestamp_meta=True,
    )
    assert "name=video_pose_source" in pipeline
    assert "name=video_pose_sink" in pipeline
    assert "rfc7273-sync=true" in pipeline
    assert "add-reference-timestamp-meta=true" in pipeline
    assert "max-buffers=1" in pipeline


def test_pts_timestamp_preserves_media_delta() -> None:
    resolver = NativeTimestampResolver(
        CaptureTimestampSource.PTS
    )
    first = resolver.resolve(
        arrival_ms=5000.0,
        pts_ns=1_000_000_000,
        reference_ns=None,
    )
    second = resolver.resolve(
        arrival_ms=6100.0,
        pts_ns=2_000_000_000,
        reference_ns=None,
    )
    assert first == 5000.0
    assert second == 6000.0


def test_pts_timestamp_remains_monotonic_after_stream_reset() -> None:
    resolver = NativeTimestampResolver(
        CaptureTimestampSource.PTS
    )
    first = resolver.resolve(
        arrival_ms=5000.0,
        pts_ns=5_000_000_000,
        reference_ns=None,
    )
    resolver.reset_stream()
    second = resolver.resolve(
        arrival_ms=5500.0,
        pts_ns=100_000_000,
        reference_ns=None,
    )
    assert second > first


def test_reference_timestamp_is_not_rebased() -> None:
    resolver = NativeTimestampResolver(
        CaptureTimestampSource.REFERENCE
    )
    value = resolver.resolve(
        arrival_ms=1000.0,
        pts_ns=100,
        reference_ns=1_700_000_000_000_000_000,
    )
    assert value == 1_700_000_000_000.0
