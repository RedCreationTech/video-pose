from __future__ import annotations

from pydantic import BaseModel, Field

from .live_health import LiveHealthSnapshot


class SoakThresholds(BaseModel):
    min_ready_ratio: float = Field(default=0.99, ge=0.0, le=1.0)
    max_drop_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    max_processing_errors: int = Field(default=0, ge=0)
    max_camera_read_errors: int = Field(default=100, ge=0)
    max_camera_reconnects: int = Field(default=20, ge=0)
    max_processing_latency_ms: float = Field(default=1000.0, gt=0.0)
    max_processing_p99_ms: float = Field(default=750.0, gt=0.0)
    max_rss_growth_mb: float = Field(default=512.0, ge=0.0)


class SoakSample(BaseModel):
    elapsed_s: float = Field(ge=0.0)
    health: LiveHealthSnapshot


class SoakReport(BaseModel):
    duration_s: float
    sample_count: int
    ready_ratio: float
    frame_sets_received_total: int
    frame_sets_processed_total: int
    frame_sets_dropped_total: int
    drop_ratio: float
    processing_errors_total: int
    camera_read_errors_total: int
    camera_reconnect_total: int
    max_processing_latency_ms: float
    max_processing_p99_ms: float
    initial_rss_mb: float | None
    max_rss_mb: float
    rss_growth_mb: float
    max_gpu_reserved_mb: float
    passed: bool
    failures: list[str]


class SoakMonitor:
    """Aggregate sampled live health into a release-gate report."""

    def __init__(self, thresholds: SoakThresholds | None = None) -> None:
        self.thresholds = thresholds or SoakThresholds()
        self.samples: list[SoakSample] = []

    def add(
        self,
        elapsed_s: float,
        snapshot: LiveHealthSnapshot,
    ) -> None:
        self.samples.append(
            SoakSample(
                elapsed_s=elapsed_s,
                health=snapshot,
            )
        )

    def report(self) -> SoakReport:
        if not self.samples:
            raise ValueError("at least one soak sample is required")

        ready_count = sum(
            1 for sample in self.samples if sample.health.ready
        )
        ready_ratio = ready_count / len(self.samples)
        latest = self.samples[-1].health
        runtime = latest.runtime
        received = runtime.frame_sets_received_total
        dropped = runtime.frame_sets_dropped_total
        drop_ratio = dropped / received if received else 0.0

        camera_read_errors = sum(
            camera.read_errors_total for camera in latest.cameras
        )
        camera_reconnects = sum(
            camera.reconnect_total for camera in latest.cameras
        )
        max_latency = max(
            (
                sample.health.runtime.max_processing_latency_ms
                for sample in self.samples
            ),
            default=0.0,
        )
        max_p99 = max(
            (
                sample.health.runtime.processing_latency_p99_ms
                for sample in self.samples
            ),
            default=0.0,
        )
        rss_values = [
            sample.health.runtime.current_rss_mb
            for sample in self.samples
            if sample.health.runtime.current_rss_mb is not None
        ]
        initial_rss = rss_values[0] if rss_values else None
        max_rss = max(rss_values, default=0.0)
        rss_growth = (
            max(0.0, max_rss - initial_rss)
            if initial_rss is not None
            else 0.0
        )
        max_gpu_reserved = max(
            (
                sample.health.runtime.max_gpu_reserved_mb
                for sample in self.samples
            ),
            default=0.0,
        )

        failures: list[str] = []
        thresholds = self.thresholds
        if ready_ratio < thresholds.min_ready_ratio:
            failures.append(
                f"ready_ratio={ready_ratio:.6f} "
                f"< {thresholds.min_ready_ratio:.6f}"
            )
        if drop_ratio > thresholds.max_drop_ratio:
            failures.append(
                f"drop_ratio={drop_ratio:.6f} "
                f"> {thresholds.max_drop_ratio:.6f}"
            )
        if (
            runtime.processing_errors_total
            > thresholds.max_processing_errors
        ):
            failures.append(
                "processing_errors_total="
                f"{runtime.processing_errors_total} "
                f"> {thresholds.max_processing_errors}"
            )
        if camera_read_errors > thresholds.max_camera_read_errors:
            failures.append(
                f"camera_read_errors_total={camera_read_errors} "
                f"> {thresholds.max_camera_read_errors}"
            )
        if camera_reconnects > thresholds.max_camera_reconnects:
            failures.append(
                f"camera_reconnect_total={camera_reconnects} "
                f"> {thresholds.max_camera_reconnects}"
            )
        if max_latency > thresholds.max_processing_latency_ms:
            failures.append(
                f"max_processing_latency_ms={max_latency:.3f} "
                f"> {thresholds.max_processing_latency_ms:.3f}"
            )
        if max_p99 > thresholds.max_processing_p99_ms:
            failures.append(
                f"max_processing_p99_ms={max_p99:.3f} "
                f"> {thresholds.max_processing_p99_ms:.3f}"
            )
        if rss_growth > thresholds.max_rss_growth_mb:
            failures.append(
                f"rss_growth_mb={rss_growth:.3f} "
                f"> {thresholds.max_rss_growth_mb:.3f}"
            )

        return SoakReport(
            duration_s=self.samples[-1].elapsed_s,
            sample_count=len(self.samples),
            ready_ratio=ready_ratio,
            frame_sets_received_total=received,
            frame_sets_processed_total=runtime.frame_sets_processed_total,
            frame_sets_dropped_total=dropped,
            drop_ratio=drop_ratio,
            processing_errors_total=runtime.processing_errors_total,
            camera_read_errors_total=camera_read_errors,
            camera_reconnect_total=camera_reconnects,
            max_processing_latency_ms=max_latency,
            max_processing_p99_ms=max_p99,
            initial_rss_mb=initial_rss,
            max_rss_mb=max_rss,
            rss_growth_mb=rss_growth,
            max_gpu_reserved_mb=max_gpu_reserved,
            passed=not failures,
            failures=failures,
        )
