from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .live_gateway import OpenCVLiveCamera


class RTSPTransport(StrEnum):
    TCP = "tcp"
    UDP = "udp"


@dataclass(frozen=True, slots=True)
class GStreamerCaptureOptions:
    transport: RTSPTransport = RTSPTransport.TCP
    latency_ms: int = 100
    max_buffers: int = 1
    drop: bool = True
    sync: bool = False
    decoder_element: str | None = None


def _decoder_for(codec: str, override: str | None) -> str:
    if override:
        return override
    normalized = codec.lower()
    if normalized in {"h264", "avc"}:
        return "avdec_h264"
    if normalized in {"h265", "hevc"}:
        return "avdec_h265"
    raise ValueError(f"unsupported RTSP codec: {codec}")


def _depay_for(codec: str) -> tuple[str, str]:
    normalized = codec.lower()
    if normalized in {"h264", "avc"}:
        return "rtph264depay", "h264parse"
    if normalized in {"h265", "hevc"}:
        return "rtph265depay", "h265parse"
    raise ValueError(f"unsupported RTSP codec: {codec}")


def build_gstreamer_rtsp_pipeline(
    uri: str,
    *,
    codec: str = "h264",
    options: GStreamerCaptureOptions | None = None,
) -> str:
    opts = options or GStreamerCaptureOptions()
    depay, parser = _depay_for(codec)
    decoder = _decoder_for(codec, opts.decoder_element)
    drop = "true" if opts.drop else "false"
    sync = "true" if opts.sync else "false"

    return " ! ".join(
        [
            (
                f'rtspsrc location="{uri}" '
                f"protocols={opts.transport.value} "
                f"latency={opts.latency_ms} "
                "drop-on-latency=true"
            ),
            depay,
            parser,
            decoder,
            "videoconvert",
            "video/x-raw,format=BGR",
            (
                "appsink "
                f"max-buffers={opts.max_buffers} "
                f"drop={drop} sync={sync}"
            ),
        ]
    )


class OpenCVGStreamerLiveCamera(OpenCVLiveCamera):
    """OpenCV wrapper over an explicit GStreamer RTSP pipeline."""

    def __init__(
        self,
        camera_id: str,
        uri: str,
        *,
        codec: str = "h264",
        options: GStreamerCaptureOptions | None = None,
    ) -> None:
        super().__init__(camera_id, uri)
        self.codec = codec
        self.options = options or GStreamerCaptureOptions()

    def open(self) -> None:
        cv2 = self._cv2()
        build_info = cv2.getBuildInformation()
        if "GStreamer:                   YES" not in build_info and (
            "GStreamer: YES" not in build_info
        ):
            raise RuntimeError(
                "OpenCV was built without GStreamer support"
            )

        pipeline = build_gstreamer_rtsp_pipeline(
            self.uri,
            codec=self.codec,
            options=self.options,
        )
        capture = cv2.VideoCapture(
            pipeline,
            cv2.CAP_GSTREAMER,
        )
        if not capture.isOpened():
            capture.release()
            raise ValueError(
                f"cannot open GStreamer camera: {self.camera_id}"
            )
        self._capture = capture


def opencv_has_gstreamer(cv2_module: Any) -> bool:
    info = cv2_module.getBuildInformation()
    return (
        "GStreamer:                   YES" in info
        or "GStreamer: YES" in info
    )
