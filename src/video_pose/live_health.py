from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

from .resource_usage import ResourceSnapshot


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
    processing_latency_p95_ms: float = 0.0
    processing_latency_p99_ms: float = 0.0
    current_rss_mb: float | None = None
    max_rss_mb: float = 0.0
    gpu_allocated_mb: float | None = None
    gpu_reserved_mb: float | None = None
    max_gpu_reserved_mb: float = 0.0
    current_thread_count: int = 0
    max_thread_count: int = 0
    current_open_fds: int | None = None
    max_open_fds: int = 0


class SyncHealthSnapshot(BaseModel):
    reference_frames_total: int = 0
    emitted_total: int = 0
    miss_total: int = 0
    missing_buffer_total: int = 0
    tolerance_miss_total: int = 0
    stale_reference_total: int = 0
    success_ratio: float = 0.0
    last_skew_ms: float | None = None
    max_skew_ms: float = 0.0
    skew_p95_ms: float = 0.0
    skew_p99_ms: float = 0.0
    camera_offsets_ms: dict[str, float] = Field(default_factory=dict)
    camera_drift_ms_per_minute: dict[str, float] = Field(
        default_factory=dict
    )


class EvidenceHealthSnapshot(BaseModel):
    enabled: bool = True
    submitted_total: int = 0
    processed_total: int = 0
    dropped_total: int = 0
    errors_total: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0
    drop_ratio: float = 0.0
    artifact_count: int = 0
    protected_count: int = 0
    total_bytes: int = 0
    max_total_bytes: int = 0
    over_capacity: bool = False


class AuditHealthSnapshot(BaseModel):
    status: str = "READY"
    write_errors_total: int = 0
    last_error: str | None = None
    last_success_at: str | None = None


class StorageHealthSnapshot(BaseModel):
    name: str
    configured_path: str
    probe_path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    free_ratio: float


class LiveHealthSnapshot(BaseModel):
    cameras: list[CameraHealthSnapshot] = Field(default_factory=list)
    runtime: RuntimeHealthSnapshot
    sync: SyncHealthSnapshot | None = None
    evidence: EvidenceHealthSnapshot | None = None
    audit: AuditHealthSnapshot | None = None
    storage: list[StorageHealthSnapshot] = Field(default_factory=list)
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
class _SyncHealth:
    reference_frames_total: int = 0
    emitted_total: int = 0
    miss_total: int = 0
    missing_buffer_total: int = 0
    tolerance_miss_total: int = 0
    stale_reference_total: int = 0
    last_skew_ms: float | None = None
    max_skew_ms: float = 0.0
    skews_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=4096)
    )
    camera_offsets_ms: dict[str, float] = field(default_factory=dict)
    offset_samples: dict[
        str,
        deque[tuple[float, float]],
    ] = field(default_factory=dict)


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
    latencies_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=4096)
    )
    current_rss_mb: float | None = None
    max_rss_mb: float = 0.0
    gpu_allocated_mb: float | None = None
    gpu_reserved_mb: float | None = None
    max_gpu_reserved_mb: float = 0.0
    current_thread_count: int = 0
    max_thread_count: int = 0
    current_open_fds: int | None = None
    max_open_fds: int = 0


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
        self._sync: _SyncHealth | None = None

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

    def enable_sync(self) -> None:
        with self._lock:
            if self._sync is None:
                self._sync = _SyncHealth()

    def sync_reference_frame(self) -> None:
        with self._lock:
            if self._sync is None:
                self._sync = _SyncHealth()
            self._sync.reference_frames_total += 1

    def sync_miss(self, reason: str) -> None:
        with self._lock:
            if self._sync is None:
                self._sync = _SyncHealth()
            sync = self._sync
            sync.miss_total += 1
            if reason == "missing_buffer":
                sync.missing_buffer_total += 1
            elif reason == "tolerance":
                sync.tolerance_miss_total += 1
            elif reason == "stale_reference":
                sync.stale_reference_total += 1

    def sync_emitted(
        self,
        *,
        reference_timestamp_ms: float,
        skew_ms: float,
        camera_offsets_ms: dict[str, float],
    ) -> None:
        with self._lock:
            if self._sync is None:
                self._sync = _SyncHealth()
            sync = self._sync
            sync.emitted_total += 1
            sync.last_skew_ms = skew_ms
            sync.max_skew_ms = max(sync.max_skew_ms, skew_ms)
            sync.skews_ms.append(skew_ms)
            sync.camera_offsets_ms = dict(camera_offsets_ms)
            for camera_id, offset_ms in camera_offsets_ms.items():
                samples = sync.offset_samples.setdefault(
                    camera_id,
                    deque(maxlen=2048),
                )
                samples.append(
                    (reference_timestamp_ms, offset_ms)
                )

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
            runtime.latencies_ms.append(latency_ms)

    def processing_error(self) -> None:
        with self._lock:
            self._runtime.processing_errors_total += 1

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self._runtime.queue_depth = depth

    def record_resources(self, snapshot: ResourceSnapshot) -> None:
        with self._lock:
            runtime = self._runtime
            runtime.current_rss_mb = snapshot.rss_mb
            runtime.max_rss_mb = max(runtime.max_rss_mb, snapshot.rss_mb)
            runtime.gpu_allocated_mb = snapshot.gpu_allocated_mb
            runtime.gpu_reserved_mb = snapshot.gpu_reserved_mb
            if snapshot.gpu_reserved_mb is not None:
                runtime.max_gpu_reserved_mb = max(
                    runtime.max_gpu_reserved_mb,
                    snapshot.gpu_reserved_mb,
                )
            runtime.current_thread_count = snapshot.thread_count
            runtime.max_thread_count = max(
                runtime.max_thread_count,
                snapshot.thread_count,
            )
            runtime.current_open_fds = snapshot.open_fds
            if snapshot.open_fds is not None:
                runtime.max_open_fds = max(
                    runtime.max_open_fds,
                    snapshot.open_fds,
                )

    def snapshot(self) -> LiveHealthSnapshot:
        with self._lock:
            cameras = [
                self._camera_snapshot(camera_id, camera)
                for camera_id, camera in sorted(self._cameras.items())
            ]
            latencies = sorted(self._runtime.latencies_ms)
            sync = None
            if self._sync is not None:
                skews = sorted(self._sync.skews_ms)
                attempts = self._sync.reference_frames_total
                sync = SyncHealthSnapshot(
                    reference_frames_total=attempts,
                    emitted_total=self._sync.emitted_total,
                    miss_total=self._sync.miss_total,
                    missing_buffer_total=self._sync.missing_buffer_total,
                    tolerance_miss_total=self._sync.tolerance_miss_total,
                    stale_reference_total=self._sync.stale_reference_total,
                    success_ratio=(
                        self._sync.emitted_total / attempts
                        if attempts
                        else 0.0
                    ),
                    last_skew_ms=self._sync.last_skew_ms,
                    max_skew_ms=self._sync.max_skew_ms,
                    skew_p95_ms=self._percentile(skews, 0.95),
                    skew_p99_ms=self._percentile(skews, 0.99),
                    camera_offsets_ms=dict(
                        self._sync.camera_offsets_ms
                    ),
                    camera_drift_ms_per_minute={
                        camera_id: self._drift_ms_per_minute(
                            list(samples)
                        )
                        for camera_id, samples
                        in self._sync.offset_samples.items()
                    },
                )
            runtime = RuntimeHealthSnapshot(
                frame_sets_received_total=self._runtime.frame_sets_received_total,
                frame_sets_processed_total=self._runtime.frame_sets_processed_total,
                frame_sets_dropped_total=self._runtime.frame_sets_dropped_total,
                processing_errors_total=self._runtime.processing_errors_total,
                queue_depth=self._runtime.queue_depth,
                queue_capacity=self._runtime.queue_capacity,
                last_processing_latency_ms=self._runtime.last_processing_latency_ms,
                max_processing_latency_ms=self._runtime.max_processing_latency_ms,
                processing_latency_p95_ms=self._percentile(latencies, 0.95),
                processing_latency_p99_ms=self._percentile(latencies, 0.99),
                current_rss_mb=self._runtime.current_rss_mb,
                max_rss_mb=self._runtime.max_rss_mb,
                gpu_allocated_mb=self._runtime.gpu_allocated_mb,
                gpu_reserved_mb=self._runtime.gpu_reserved_mb,
                max_gpu_reserved_mb=self._runtime.max_gpu_reserved_mb,
                current_thread_count=(
                    self._runtime.current_thread_count
                ),
                max_thread_count=self._runtime.max_thread_count,
                current_open_fds=self._runtime.current_open_fds,
                max_open_fds=self._runtime.max_open_fds,
            )
        ready = bool(cameras) and all(
            camera.state in {CameraState.ONLINE, CameraState.DEGRADED}
            for camera in cameras
        )
        return LiveHealthSnapshot(
            cameras=cameras,
            runtime=runtime,
            sync=sync,
            ready=ready,
        )

    def _camera(self, camera_id: str) -> _CameraHealth:
        if camera_id not in self._cameras:
            raise KeyError(f"unknown health camera: {camera_id}")
        return self._cameras[camera_id]

    @staticmethod
    def _drift_ms_per_minute(
        samples: list[tuple[float, float]],
    ) -> float:
        if len(samples) < 2:
            return 0.0
        first_time = samples[0][0]
        last_time = samples[-1][0]
        if last_time - first_time < 30_000.0:
            return 0.0

        xs = [
            (timestamp_ms - first_time) / 60_000.0
            for timestamp_ms, _offset_ms in samples
        ]
        ys = [offset_ms for _timestamp_ms, offset_ms in samples]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum(
            (value - mean_x) ** 2 for value in xs
        )
        if denominator <= 0:
            return 0.0
        numerator = sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(xs, ys, strict=True)
        )
        return numerator / denominator

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        index = max(
            0,
            min(
                len(values) - 1,
                int(round((len(values) - 1) * percentile)),
            ),
        )
        return values[index]

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
