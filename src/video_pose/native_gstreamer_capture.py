from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .gstreamer_capture import (
    GStreamerCaptureOptions,
    _decoder_for,
    _depay_for,
)
from .runtime_config import CaptureTimestampSource


@dataclass(slots=True)
class NativeTimestampResolver:
    source: CaptureTimestampSource
    _pts_origin_ns: int | None = None
    _timeline_origin_ms: float | None = None
    _last_output_ms: float | None = None

    def reset_stream(self) -> None:
        self._pts_origin_ns = None
        self._timeline_origin_ms = None

    def resolve(
        self,
        *,
        arrival_ms: float,
        pts_ns: int | None,
        reference_ns: int | None,
    ) -> float:
        if self.source == CaptureTimestampSource.ARRIVAL:
            self._last_output_ms = arrival_ms
            return arrival_ms

        if self.source == CaptureTimestampSource.REFERENCE:
            if reference_ns is None:
                raise RuntimeError(
                    "reference timestamp requested but "
                    "GstReferenceTimestampMeta is unavailable"
                )
            value = reference_ns / 1_000_000.0
            self._last_output_ms = value
            return value

        if pts_ns is None:
            raise RuntimeError(
                "PTS timestamp requested but GstBuffer.pts is unavailable"
            )

        if self._pts_origin_ns is None:
            self._start_pts_epoch(pts_ns, arrival_ms)
        assert self._pts_origin_ns is not None
        assert self._timeline_origin_ms is not None

        value = (
            self._timeline_origin_ms
            + (pts_ns - self._pts_origin_ns) / 1_000_000.0
        )
        if (
            self._last_output_ms is not None
            and value <= self._last_output_ms
        ):
            self._start_pts_epoch(
                pts_ns,
                max(arrival_ms, self._last_output_ms + 0.001),
            )
            assert self._timeline_origin_ms is not None
            value = self._timeline_origin_ms

        self._last_output_ms = value
        return value

    def _start_pts_epoch(
        self,
        pts_ns: int,
        arrival_ms: float,
    ) -> None:
        baseline = arrival_ms
        if self._last_output_ms is not None:
            baseline = max(
                baseline,
                self._last_output_ms + 0.001,
            )
        self._pts_origin_ns = pts_ns
        self._timeline_origin_ms = baseline


def build_native_gstreamer_rtsp_pipeline(
    uri: str,
    *,
    codec: str = "h264",
    options: GStreamerCaptureOptions | None = None,
    ntp_sync: bool = False,
    rfc7273_sync: bool = False,
    add_reference_timestamp_meta: bool = False,
) -> str:
    opts = options or GStreamerCaptureOptions()
    depay, parser = _depay_for(codec)
    decoder = _decoder_for(codec, opts.decoder_element)
    source = [
        "rtspsrc",
        "name=video_pose_source",
        f'location="{uri}"',
        f"protocols={opts.transport.value}",
        f"latency={opts.latency_ms}",
        "drop-on-latency=true",
    ]
    if ntp_sync:
        source.append("ntp-sync=true")
    if rfc7273_sync:
        source.append("rfc7273-sync=true")
    if add_reference_timestamp_meta:
        source.append("add-reference-timestamp-meta=true")

    drop = "true" if opts.drop else "false"
    sync = "true" if opts.sync else "false"
    return " ! ".join(
        [
            " ".join(source),
            depay,
            parser,
            decoder,
            "videoconvert",
            "video/x-raw,format=BGR",
            (
                "appsink name=video_pose_sink "
                f"max-buffers={opts.max_buffers} "
                f"drop={drop} sync={sync}"
            ),
        ]
    )


def _load_native_runtime() -> tuple[Any, Any]:
    try:
        import gi
    except ImportError as exc:
        raise RuntimeError(
            "gstreamer-native requires PyGObject/gi"
        ) from exc

    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    try:
        from gi.repository import Gst
    except ImportError as exc:
        raise RuntimeError(
            "GStreamer GI namespace is unavailable"
        ) from exc

    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "gstreamer-native requires numpy"
        ) from exc

    Gst.init(None)
    return Gst, np


def inspect_native_gstreamer(
    *,
    require_reference_timestamp: bool = False,
) -> str:
    Gst, _np = _load_native_runtime()
    missing = [
        name
        for name in ("rtspsrc", "appsink", "videoconvert")
        if Gst.ElementFactory.find(name) is None
    ]
    if missing:
        raise RuntimeError(
            "missing GStreamer elements: " + ", ".join(missing)
        )

    if require_reference_timestamp:
        source = Gst.ElementFactory.make("rtspsrc", None)
        if source is None:
            raise RuntimeError("cannot create rtspsrc")
        for property_name in (
            "rfc7273-sync",
            "add-reference-timestamp-meta",
        ):
            if source.find_property(property_name) is None:
                raise RuntimeError(
                    "rtspsrc does not support required property: "
                    + property_name
                )

    version = Gst.version()
    return (
        "native GStreamer available: "
        f"{version[0]}.{version[1]}.{version[2]}"
    )


class NativeGStreamerLiveCamera:
    """Native GstAppSink reader with explicit timestamp semantics."""

    def __init__(
        self,
        camera_id: str,
        uri: str,
        *,
        codec: str = "h264",
        options: GStreamerCaptureOptions | None = None,
        timestamp_source: CaptureTimestampSource = (
            CaptureTimestampSource.PTS
        ),
        pull_timeout_ms: int = 1000,
        ntp_sync: bool = False,
        rfc7273_sync: bool = False,
    ) -> None:
        self.camera_id = camera_id
        self.uri = uri
        self.codec = codec
        self.options = options or GStreamerCaptureOptions()
        self.timestamp_source = timestamp_source
        self.pull_timeout_ms = pull_timeout_ms
        self.ntp_sync = ntp_sync
        self.rfc7273_sync = (
            rfc7273_sync
            or timestamp_source == CaptureTimestampSource.REFERENCE
        )
        self.resolver = NativeTimestampResolver(timestamp_source)
        self._pipeline: Any | None = None
        self._appsink: Any | None = None
        self._gst: Any | None = None
        self._np: Any | None = None

    def open(self) -> None:
        Gst, np = _load_native_runtime()
        pipeline_text = build_native_gstreamer_rtsp_pipeline(
            self.uri,
            codec=self.codec,
            options=self.options,
            ntp_sync=self.ntp_sync,
            rfc7273_sync=self.rfc7273_sync,
            add_reference_timestamp_meta=(
                self.timestamp_source
                == CaptureTimestampSource.REFERENCE
            ),
        )
        pipeline = Gst.parse_launch(pipeline_text)
        appsink = pipeline.get_by_name("video_pose_sink")
        if appsink is None:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError(
                "native GStreamer pipeline has no appsink"
            )

        result = pipeline.set_state(Gst.State.PLAYING)
        if result == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError(
                f"failed to start GStreamer camera: {self.camera_id}"
            )

        self.resolver.reset_stream()
        self._gst = Gst
        self._np = np
        self._pipeline = pipeline
        self._appsink = appsink

    def read(self) -> tuple[float, Any]:
        if self._pipeline is None or self._appsink is None:
            self.open()
        assert self._appsink is not None
        assert self._gst is not None

        Gst = self._gst
        sample = self._appsink.emit(
            "try-pull-sample",
            int(self.pull_timeout_ms * Gst.MSECOND),
        )
        if sample is None:
            raise RuntimeError(
                f"GStreamer sample timeout: {self.camera_id}"
            )

        buffer = sample.get_buffer()
        if buffer is None:
            raise RuntimeError(
                f"GStreamer sample has no buffer: {self.camera_id}"
            )

        arrival_ms = time.monotonic_ns() / 1_000_000.0
        pts_ns = (
            None
            if buffer.pts == Gst.CLOCK_TIME_NONE
            else int(buffer.pts)
        )
        reference_ns = self._reference_timestamp_ns(buffer)
        timestamp_ms = self.resolver.resolve(
            arrival_ms=arrival_ms,
            pts_ns=pts_ns,
            reference_ns=reference_ns,
        )
        return timestamp_ms, self._decode_bgr(sample, buffer)

    def close(self) -> None:
        if self._pipeline is not None and self._gst is not None:
            self._pipeline.set_state(self._gst.State.NULL)
        self._pipeline = None
        self._appsink = None

    def _reference_timestamp_ns(self, buffer: Any) -> int | None:
        if (
            self.timestamp_source
            != CaptureTimestampSource.REFERENCE
        ):
            return None
        meta = buffer.get_reference_timestamp_meta(None)
        if meta is None:
            return None
        assert self._gst is not None
        if meta.timestamp == self._gst.CLOCK_TIME_NONE:
            return None
        return int(meta.timestamp)

    def _decode_bgr(
        self,
        sample: Any,
        buffer: Any,
    ) -> Any:
        assert self._gst is not None
        assert self._np is not None
        caps = sample.get_caps()
        if caps is None or caps.get_size() < 1:
            raise RuntimeError("GStreamer sample has no caps")
        structure = caps.get_structure(0)
        width = int(structure.get_value("width"))
        height = int(structure.get_value("height"))
        row_bytes = width * 3

        mapped, info = buffer.map(self._gst.MapFlags.READ)
        if not mapped:
            raise RuntimeError("failed to map GStreamer buffer")
        try:
            values = self._np.frombuffer(
                info.data,
                dtype=self._np.uint8,
            )
            expected = row_bytes * height
            if values.size < expected:
                raise RuntimeError(
                    "GStreamer BGR buffer is smaller than expected"
                )
            if values.size == expected:
                return values.reshape(
                    (height, width, 3)
                ).copy()

            stride = values.size // height
            if stride < row_bytes:
                raise RuntimeError(
                    "GStreamer BGR row stride is invalid"
                )
            output = self._np.empty(
                (height, width, 3),
                dtype=self._np.uint8,
            )
            for row in range(height):
                start = row * stride
                output[row] = values[
                    start : start + row_bytes
                ].reshape((width, 3))
            return output
        finally:
            buffer.unmap(info)
