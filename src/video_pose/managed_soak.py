from __future__ import annotations

from pydantic import BaseModel, Field

from .live_health import LiveHealthSnapshot
from .soak import SoakMonitor, SoakReport, SoakThresholds


class ManagedSoakThresholds(BaseModel):
    max_session_start_errors: int = Field(default=0, ge=0)
    max_session_stop_errors: int = Field(default=0, ge=0)
    max_session_start_latency_ms: float = Field(default=5000.0, gt=0.0)
    max_session_stop_latency_ms: float = Field(default=5000.0, gt=0.0)
    min_completed_sessions: int = Field(default=1, ge=1)


class ManagedSoakReport(BaseModel):
    health: SoakReport
    hub_start_errors_total: int
    model_pool_loaded: bool
    sessions_started: int
    sessions_completed: int
    session_start_errors_total: int
    session_stop_errors_total: int
    max_session_start_latency_ms: float
    max_session_stop_latency_ms: float
    passed: bool
    failures: list[str]


class ManagedSoakMonitor:
    """Release gate for persistent cameras/models plus repeated sessions."""

    def __init__(
        self,
        *,
        health_thresholds: SoakThresholds | None = None,
        managed_thresholds: ManagedSoakThresholds | None = None,
    ) -> None:
        self.health = SoakMonitor(health_thresholds)
        self.thresholds = managed_thresholds or ManagedSoakThresholds()
        self.hub_start_errors_total = 0
        self.model_pool_loaded = False
        self.sessions_started = 0
        self.sessions_completed = 0
        self.session_start_errors_total = 0
        self.session_stop_errors_total = 0
        self.max_session_start_latency_ms = 0.0
        self.max_session_stop_latency_ms = 0.0

    def add_health(
        self,
        elapsed_s: float,
        snapshot: LiveHealthSnapshot,
    ) -> None:
        self.health.add(elapsed_s, snapshot)

    def record_hub_start(self, *, success: bool) -> None:
        if not success:
            self.hub_start_errors_total += 1

    def record_model_pool_loaded(self, loaded: bool) -> None:
        self.model_pool_loaded = loaded

    def record_session_start(
        self,
        latency_ms: float,
        *,
        success: bool,
    ) -> None:
        self.max_session_start_latency_ms = max(
            self.max_session_start_latency_ms,
            latency_ms,
        )
        if success:
            self.sessions_started += 1
        else:
            self.session_start_errors_total += 1

    def record_session_stop(
        self,
        latency_ms: float,
        *,
        success: bool,
    ) -> None:
        self.max_session_stop_latency_ms = max(
            self.max_session_stop_latency_ms,
            latency_ms,
        )
        if success:
            self.sessions_completed += 1
        else:
            self.session_stop_errors_total += 1

    def report(self) -> ManagedSoakReport:
        health_report = self.health.report()
        failures = list(health_report.failures)
        thresholds = self.thresholds

        if self.hub_start_errors_total:
            failures.append(
                f"hub_start_errors_total={self.hub_start_errors_total} > 0"
            )
        if not self.model_pool_loaded:
            failures.append("model_pool_loaded=false")
        if (
            self.session_start_errors_total
            > thresholds.max_session_start_errors
        ):
            failures.append(
                "session_start_errors_total="
                f"{self.session_start_errors_total} "
                f"> {thresholds.max_session_start_errors}"
            )
        if (
            self.session_stop_errors_total
            > thresholds.max_session_stop_errors
        ):
            failures.append(
                "session_stop_errors_total="
                f"{self.session_stop_errors_total} "
                f"> {thresholds.max_session_stop_errors}"
            )
        if (
            self.max_session_start_latency_ms
            > thresholds.max_session_start_latency_ms
        ):
            failures.append(
                "max_session_start_latency_ms="
                f"{self.max_session_start_latency_ms:.3f} "
                f"> {thresholds.max_session_start_latency_ms:.3f}"
            )
        if (
            self.max_session_stop_latency_ms
            > thresholds.max_session_stop_latency_ms
        ):
            failures.append(
                "max_session_stop_latency_ms="
                f"{self.max_session_stop_latency_ms:.3f} "
                f"> {thresholds.max_session_stop_latency_ms:.3f}"
            )
        if self.sessions_completed < thresholds.min_completed_sessions:
            failures.append(
                f"sessions_completed={self.sessions_completed} "
                f"< {thresholds.min_completed_sessions}"
            )

        return ManagedSoakReport(
            health=health_report,
            hub_start_errors_total=self.hub_start_errors_total,
            model_pool_loaded=self.model_pool_loaded,
            sessions_started=self.sessions_started,
            sessions_completed=self.sessions_completed,
            session_start_errors_total=self.session_start_errors_total,
            session_stop_errors_total=self.session_stop_errors_total,
            max_session_start_latency_ms=self.max_session_start_latency_ms,
            max_session_stop_latency_ms=self.max_session_stop_latency_ms,
            passed=not failures,
            failures=failures,
        )
