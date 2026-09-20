from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from .live_video import LiveFrameSynchronizer
from .video_manifest import ReplayManifest
from .video_replay import SynchronizedFrameSet


class OpenCVLiveCamera:
    """Minimal RTSP/video live reader using capture time as the source clock."""

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
            raise ValueError(f"cannot open live camera: {self.uri}")
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


class ThreadedLiveGateway:
    """Read enabled cameras concurrently and emit synchronized frame sets."""

    def __init__(
        self,
        manifest: ReplayManifest,
        synchronizer: LiveFrameSynchronizer,
        *,
        camera_factory: Callable[[str, str], OpenCVLiveCamera] | None = None,
    ) -> None:
        self.manifest = manifest
        self.synchronizer = synchronizer
        self.camera_factory = camera_factory or OpenCVLiveCamera
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._cameras: list[OpenCVLiveCamera] = []
        self._callback: Callable[[SynchronizedFrameSet], None] | None = None

    def start(
        self,
        callback: Callable[[SynchronizedFrameSet], None],
    ) -> None:
        if self._threads:
            raise RuntimeError("live gateway is already running")
        self._callback = callback
        self._stop.clear()

        for config in self.manifest.cameras:
            if not config.enabled:
                continue
            camera = self.camera_factory(config.camera_id, config.uri)
            camera.open()
            self._cameras.append(camera)
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
            thread.join(timeout=2.0)
        for camera in self._cameras:
            camera.close()
        self._threads.clear()
        self._cameras.clear()

    def _run_camera(self, camera: OpenCVLiveCamera) -> None:
        while not self._stop.is_set():
            try:
                timestamp_ms, image = camera.read()
                frame_set = self.synchronizer.push(
                    camera_id=camera.camera_id,
                    source_timestamp_ms=timestamp_ms,
                    image=image,
                )
                if frame_set is not None and self._callback is not None:
                    self._callback(frame_set)
            except Exception:
                if self._stop.is_set():
                    return
                time.sleep(0.1)
