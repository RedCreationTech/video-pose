from video_pose.gstreamer_capture import (
    GStreamerCaptureOptions,
    RTSPTransport,
    build_gstreamer_rtsp_pipeline,
)


def test_h264_gstreamer_pipeline_is_bounded_and_realtime() -> None:
    pipeline = build_gstreamer_rtsp_pipeline(
        "rtsp://camera/stream",
        codec="h264",
        options=GStreamerCaptureOptions(
            transport=RTSPTransport.TCP,
            latency_ms=120,
            max_buffers=1,
            drop=True,
            sync=False,
        ),
    )
    assert "protocols=tcp" in pipeline
    assert "latency=120" in pipeline
    assert "rtph264depay" in pipeline
    assert "avdec_h264" in pipeline
    assert "max-buffers=1" in pipeline
    assert "drop=true" in pipeline
    assert "sync=false" in pipeline


def test_h265_pipeline_uses_h265_elements() -> None:
    pipeline = build_gstreamer_rtsp_pipeline(
        "rtsp://camera/stream",
        codec="h265",
    )
    assert "rtph265depay" in pipeline
    assert "h265parse" in pipeline
    assert "avdec_h265" in pipeline


def test_decoder_element_can_be_overridden() -> None:
    pipeline = build_gstreamer_rtsp_pipeline(
        "rtsp://camera/stream",
        codec="h264",
        options=GStreamerCaptureOptions(
            decoder_element="nvh264dec",
        ),
    )
    assert "nvh264dec" in pipeline
