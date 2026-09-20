from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class CameraState(StrEnum):
    STARTING = "STARTING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class CameraHealthSnapshot(BaseModel):
    camera_id: str
    state: CameraState
    frames_total: int = 0
    read_errors_total: int = 0
    reconnect_total: int = 0
    consecutive_errors: int = 0
    fps_estimate: float = 0.0
    last_frame_monotonic_ms: float | None = None
    last_error: str | None = None


class RuntimeHealthSnapshot(BaseModel):
    frame_sets_received_total: int = 0
    frame_sets_processed_total: int = 0
    frame_sets_dropped_total: int = 0
    processing_errors_total: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0
    last_processing_latency_ms: float | None = None
    max_processing_latency_ms: float = 0.0


class LiveHealthSnapshot(BaseModel):
    cameras: list[CameraHealthSnapshot] = Field(default_factory=list)
    runtime: RuntimeHealthSnapshot
    ready: bool


@dataclass(slots=True)
class _CameraHealth:
    state: CameraState = CameraState.STARTING
    frames_total: int = 0
    read_errors_total: int = 0
    reconnect_total: int = 0
    consecutive_errors: int = 0
    first_frame_monotonic_ms: float | None = None
    last_frame_monotonic_ms: float | None = None
    last_error: str | None = None


@dataclass(slots=True)
class _RuntimeHealth:
    frame_sets_received_total: int = 0
    frame_sets_processed_total: int = 0
    frame_sets_dropped_total: int = 0
    processing_errors_total: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0
    last_processing_latency_ms: float | None = None
    max_processing_latency_ms: float = 0.0


class LiveHealthRegistry:
    """Thread-safe health state shared by capture and inference workers."""

    def __init__(
        self,
        camera_ids: list[str],
        *,
        queue_capacity: int = 0,
    ) -> None:
        self._lock = threading.Lock()
        self._cameras = {
            camera_id: _CameraHealth()
            for camera_id in camera_ids
        }
        self._runtime = _RuntimeHealth(queue_capacity=queue_capacity)

    def camera_starting(self, camera_id: str) -> None:
        with self._lock:
            self._camera(camera_id).state = CameraState.STARTING

    def camera_frame(
        self,
        camera_id: str,
        *,
        monotonic_ms: float,
    ) -> None:
        with self._lock:
            camera = self._camera(camera_id)
            camera.state = CameraState.ONLINE
            camera.frames_total += 1
            camera.consecutive_errors = 0
            camera.last_error = None
            if camera.first_frame_monotonic_ms is None:
                camera.first_frame_monotonic_ms = monotonic_ms
            camera.last_frame_monotonic_ms = monotonic_ms

    def camera_error(self, camera_id: str, error: Exception) -> None:
        with self._lock:
            camera = self._camera(camera_id)
            camera.state = CameraState.DEGRADED
            camera.read_errors_total += 1
            camera.consecutive_errors += 1
            camera.last_error = str(error)

    def camera_reconnecting(self, camera_id: str) -> None:
        with self._lock:
            camera = self._camera(camera_id)
            camera.state = CameraState.RECONNECTING
            camera.reconnect_total += 1

    def camera_stopped(self, camera_id: str) -> None:
        with self._lock:
            self._camera(camera_id).state = CameraState.STOPPED

    def frame_set_received(self) -> None:
        with self._lock:
            self._runtime.frame_sets_received_total += 1

    def frame_set_dropped(self) -> None:
        with self._lock:
            self._runtime.frame_sets_dropped_total += 1

    def frame_set_processed(self, latency_ms: float) -> None:
        with self._lock:
            runtime = self._runtime
            runtime.frame_sets_processed_total += 1
            runtime.last_processing_latency_ms = latency_ms
            runtime.max_processing_latency_ms = max(
                runtime.max_processing_latency_ms,
                latency_ms,
            )

    def processing_error(self) -> None:
        with self._lock:
            self._runtime.processing_errors_total += 1

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self._runtime.queue_depth = depth

    def snapshot(self) -> LiveHealthSnapshot:
        with self._lock:
            cameras = [
                self._camera_snapshot(camera_id, camera)
                for camera_id, camera in sorted(self._cameras.items())
            ]
            runtime = RuntimeHealthSnapshot(
                frame_sets_received_total=self._runtime.frame_sets_received_total,
                frame_sets_processed_total=self._runtime.frame_sets_processed_total,
                frame_sets_dropped_total=self._runtime.frame_sets_dropped_total,
                processing_errors_total=self._runtime.processing_errors_total,
                queue_depth=self._runtime.queue_depth,
                queue_capacity=self._runtime.queue_capacity,
                last_processing_latency_ms=self._runtime.last_processing_latency_ms,
                max_processing_latency_ms=self._runtime.max_processing_latency_ms,
            )
        ready = bool(cameras) and all(
            camera.state in {CameraState.ONLINE, CameraState.DEGRADED}
            for camera in cameras
        )
        return LiveHealthSnapshot(
            cameras=cameras,
            runtime=runtime,
            ready=ready,
        )

    def _camera(self, camera_id: str) -> _CameraHealth:
        if camera_id not in self._cameras:
            raise KeyError(f"unknown health camera: {camera_id}")
        return self._cameras[camera_id]

    @staticmethod
    def _camera_snapshot(
        camera_id: str,
        camera: _CameraHealth,
    ) -> CameraHealthSnapshot:
        fps = 0.0
        if (
            camera.first_frame_monotonic_ms is not None
            and camera.last_frame_monotonic_ms is not None
            and camera.frames_total > 1
        ):
            duration_s = (
                camera.last_frame_monotonic_ms
                - camera.first_frame_monotonic_ms
            ) / 1000.0
            if duration_s > 0:
                fps = (camera.frames_total - 1) / duration_s
        return CameraHealthSnapshot(
            camera_id=camera_id,
            state=camera.state,
            frames_total=camera.frames_total,
            read_errors_total=camera.read_errors_total,
            reconnect_total=camera.reconnect_total,
            consecutive_errors=camera.consecutive_errors,
            fps_estimate=fps,
            last_frame_monotonic_ms=camera.last_frame_monotonic_ms,
            last_error=camera.last_error,
        )
