from __future__ import annotations

from collections.abc import Callable

from .gstreamer_capture import (
    GStreamerCaptureOptions,
    OpenCVGStreamerLiveCamera,
    RTSPTransport,
)
from .live_gateway import LiveCameraReader, OpenCVLiveCamera
from .native_gstreamer_capture import NativeGStreamerLiveCamera
from .runtime_config import CaptureBackend, LiveCaptureRuntimeConfig
from .video_manifest import ReplayManifest


def build_live_camera_factory(
    manifest: ReplayManifest,
    config: LiveCaptureRuntimeConfig,
) -> Callable[[str, str], LiveCameraReader]:
    if config.backend == CaptureBackend.OPENCV:
        return OpenCVLiveCamera

    camera_by_id = {
        camera.camera_id: camera
        for camera in manifest.cameras
    }
    transport = RTSPTransport(config.rtsp_transport.lower())
    options = GStreamerCaptureOptions(
        transport=transport,
        latency_ms=config.latency_ms,
        max_buffers=config.appsink_max_buffers,
        drop=config.appsink_drop,
        sync=config.appsink_sync,
        decoder_element=config.decoder_element,
    )

    if config.backend == CaptureBackend.GSTREAMER_OPENCV:
        def factory(camera_id: str, uri: str) -> LiveCameraReader:
            camera = camera_by_id[camera_id]
            return OpenCVGStreamerLiveCamera(
                camera_id,
                uri,
                codec=camera.codec,
                options=options,
            )

        return factory

    def native_factory(
        camera_id: str,
        uri: str,
    ) -> LiveCameraReader:
        camera = camera_by_id[camera_id]
        return NativeGStreamerLiveCamera(
            camera_id,
            uri,
            codec=camera.codec,
            options=options,
            timestamp_source=config.native_timestamp_source,
            pull_timeout_ms=config.native_pull_timeout_ms,
            ntp_sync=config.native_ntp_sync,
            rfc7273_sync=(
                config.native_rfc7273_sync
                or config.native_timestamp_source.value == "reference"
            ),
        )

    return native_factory
