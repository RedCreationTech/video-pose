from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .live_health import LiveHealthRegistry
from .live_video import LiveFrameSynchronizer
from .structured_log import log_event
from .video_manifest import ReplayManifest
from .video_replay import SynchronizedFrameSet

LOGGER = logging.getLogger("video_pose.camera")


class LiveCameraReader(Protocol):
    camera_id: str
    uri: str

    def open(self) -> None: ...

    def read(self) -> tuple[float, Any]: ...

    def close(self) -> None: ...


class OpenCVLiveCamera:
    """Minimal RTSP/video reader using monotonic capture time."""

    def __init__(self, camera_id: str, uri: str) -> None:
        self.camera_id = camera_id
        self.uri = uri
        self._capture: Any | None = None
        self._cv2_module: Any | None = None

    def _cv2(self) -> Any:
        if self._cv2_module is not None:
            return self._cv2_module
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCVLiveCamera requires the optional video dependencies"
            ) from exc
        self._cv2_module = cv2
        return cv2

    def open(self) -> None:
        cv2 = self._cv2()
        capture = cv2.VideoCapture(self.uri)
        if not capture.isOpened():
            capture.release()
            raise ValueError(
                f"cannot open live camera: {self.camera_id}"
            )
        self._capture = capture

    def read(self) -> tuple[float, Any]:
        if self._capture is None:
            self.open()
        assert self._capture is not None
        ok, image = self._capture.read()
        if not ok:
            raise RuntimeError(f"live camera read failed: {self.camera_id}")
        return time.monotonic_ns() / 1_000_000.0, image

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    initial_delay_s: float = 0.2
    max_delay_s: float = 5.0
    multiplier: float = 2.0


class ThreadedLiveGateway:
    """Read cameras concurrently with reconnect and health accounting."""

    def __init__(
        self,
        manifest: ReplayManifest,
        synchronizer: LiveFrameSynchronizer,
        *,
        camera_factory: Callable[[str, str], LiveCameraReader] | None = None,
        health: LiveHealthRegistry | None = None,
        reconnect_policy: ReconnectPolicy | None = None,
    ) -> None:
        self.manifest = manifest
        self.synchronizer = synchronizer
        self.camera_factory = camera_factory or OpenCVLiveCamera
        self.health = health or LiveHealthRegistry(
            [
                camera.camera_id
                for camera in manifest.cameras
                if camera.enabled
            ]
        )
        self.reconnect_policy = reconnect_policy or ReconnectPolicy()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._cameras: list[LiveCameraReader] = []
        self._callback: Callable[[SynchronizedFrameSet], None] | None = None

    def start(
        self,
        callback: Callable[[SynchronizedFrameSet], None],
    ) -> None:
        if self._threads:
            raise RuntimeError("live gateway is already running")
        self._callback = callback
        self._stop.clear()

        enabled_count = sum(
            1
            for camera in self.manifest.cameras
            if camera.enabled
        )
        log_event(
            LOGGER,
            "camera_gateway_starting",
            camera_count=enabled_count,
        )

        for config in self.manifest.cameras:
            if not config.enabled:
                continue
            camera = self.camera_factory(config.camera_id, config.uri)
            self._cameras.append(camera)
            self.health.camera_starting(config.camera_id)
            thread = threading.Thread(
                target=self._run_camera,
                args=(camera,),
                name=f"video-pose-{config.camera_id}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=3.0)
        for camera in self._cameras:
            camera.close()
            self.health.camera_stopped(camera.camera_id)
        self._threads.clear()
        self._cameras.clear()
        log_event(
            LOGGER,
            "camera_gateway_stopped",
        )

    def _run_camera(self, camera: LiveCameraReader) -> None:
        delay = self.reconnect_policy.initial_delay_s
        recovering = False
        while not self._stop.is_set():
            try:
                timestamp_ms, image = camera.read()
                arrival_monotonic_ms = (
                    time.monotonic_ns() / 1_000_000.0
                )
                self.health.camera_frame(
                    camera.camera_id,
                    monotonic_ms=arrival_monotonic_ms,
                )
                if recovering:
                    log_event(
                        LOGGER,
                        "camera_stream_recovered",
                        camera_id=camera.camera_id,
                    )
                    recovering = False
                delay = self.reconnect_policy.initial_delay_s
                frame_set = self.synchronizer.push(
                    camera_id=camera.camera_id,
                    source_timestamp_ms=timestamp_ms,
                    image=image,
                )
                if frame_set is not None and self._callback is not None:
                    self._callback(frame_set)
            except Exception as exc:
                self.health.camera_error(camera.camera_id, exc)
                log_event(
                    LOGGER,
                    "camera_stream_error",
                    level=logging.WARNING,
                    camera_id=camera.camera_id,
                    error_type=type(exc).__name__,
                    reconnect_delay_s=delay,
                )
                recovering = True
                camera.close()
                if self._stop.is_set():
                    return
                self.health.camera_reconnecting(camera.camera_id)
                self._stop.wait(delay)
                delay = min(
                    self.reconnect_policy.max_delay_s,
                    delay * self.reconnect_policy.multiplier,
                )
