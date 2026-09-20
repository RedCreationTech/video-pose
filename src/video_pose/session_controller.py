from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .live_health import LiveHealthRegistry, LiveHealthSnapshot
from .live_payload import live_update_payload
from .live_runtime import LiveAnalysisRuntime, LiveAnalysisUpdate, build_live_runtime
from .realtime_rules import RuleSessionUpdate
from .runtime_config import LoadedAnalysisConfig
from .session_audit import SessionAuditMetadata, SessionAuditWriter


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManagedSessionStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class SessionStartRequest(BaseModel):
    session_id: str | None = None
    operator_id: str | None = None


class ManagedSessionState(BaseModel):
    session_id: str
    operator_id: str | None = None
    operation: str
    workstation_id: str
    status: ManagedSessionStatus
    started_at: str
    ended_at: str | None = None


class LiveSessionController:
    """Own one active live analysis runtime and its audit lifecycle."""

    def __init__(
        self,
        config: LoadedAnalysisConfig,
        *,
        audit_root: str | Path,
        processing_queue_size: int = 2,
        runtime_factory: Callable[..., LiveAnalysisRuntime] = build_live_runtime,
    ) -> None:
        self.config = config
        self.audit = SessionAuditWriter(audit_root)
        self.processing_queue_size = processing_queue_size
        self.runtime_factory = runtime_factory
        self._lock = threading.RLock()
        self._runtime: LiveAnalysisRuntime | None = None
        self._state: ManagedSessionState | None = None
        self._event_callback: Callable[[LiveAnalysisUpdate], Any] | None = None

    def set_event_callback(
        self,
        callback: Callable[[LiveAnalysisUpdate], Any] | None,
    ) -> None:
        with self._lock:
            self._event_callback = callback

    def start(
        self,
        request: SessionStartRequest | None = None,
    ) -> ManagedSessionState:
        request = request or SessionStartRequest()
        with self._lock:
            if (
                self._state is not None
                and self._state.status == ManagedSessionStatus.RUNNING
            ):
                raise RuntimeError("a live session is already running")

            session_id = request.session_id or str(uuid.uuid4())
            runtime = self.runtime_factory(
                self.config,
                processing_queue_size=self.processing_queue_size,
                session_id=session_id,
            )
            rule_set = runtime.rule_session.engine.rule_set
            manifest = runtime.gateway.manifest
            started_at = _utc_now()
            state = ManagedSessionState(
                session_id=session_id,
                operator_id=request.operator_id,
                operation=rule_set.operation,
                workstation_id=manifest.workstation_id,
                status=ManagedSessionStatus.RUNNING,
                started_at=started_at,
            )
            metadata = SessionAuditMetadata(
                session_id=session_id,
                operator_id=request.operator_id,
                operation=rule_set.operation,
                workstation_id=manifest.workstation_id,
                rule_set_version=rule_set.version,
                started_at=started_at,
                config_path=str(self.config.path),
                detector_weights=self.config.config.detector.weights,
                pose_config=(
                    self.config.config.pose.config
                    if self.config.config.pose is not None
                    else None
                ),
                pose_checkpoint=(
                    self.config.config.pose.checkpoint
                    if self.config.config.pose is not None
                    else None
                ),
                planar_calibration=self.config.config.calibration,
                perspective_calibration=(
                    self.config.config.triangulation.calibration
                    if self.config.config.triangulation.enabled
                    else None
                ),
            )
            self.audit.start(metadata)
            self._runtime = runtime
            self._state = state

            try:
                runtime.start(self._handle_update)
            except Exception:
                self._runtime = None
                self._state = None
                self.audit.finish(
                    session_id,
                    {"error": "runtime start failed"},
                    status=ManagedSessionStatus.ABORTED.value,
                )
                raise
            return state.model_copy(deep=True)

    def stop(self, session_id: str) -> RuleSessionUpdate:
        return self._finish(
            session_id,
            status=ManagedSessionStatus.COMPLETED,
        )

    def abort(self, session_id: str) -> RuleSessionUpdate:
        return self._finish(
            session_id,
            status=ManagedSessionStatus.ABORTED,
        )

    def current(self) -> ManagedSessionState | None:
        with self._lock:
            return (
                self._state.model_copy(deep=True)
                if self._state is not None
                else None
            )

    def health_snapshot(self) -> LiveHealthSnapshot:
        with self._lock:
            if self._runtime is not None:
                return self._runtime.health_snapshot()
        return LiveHealthRegistry([], queue_capacity=0).snapshot()

    def _handle_update(self, update: LiveAnalysisUpdate) -> None:
        with self._lock:
            state = self._state
            callback = self._event_callback
        if state is None:
            return
        self.audit.append_payload(
            state.session_id,
            live_update_payload(update),
        )
        if callback is not None:
            callback(update)

    def _finish(
        self,
        session_id: str,
        *,
        status: ManagedSessionStatus,
    ) -> RuleSessionUpdate:
        with self._lock:
            if self._runtime is None or self._state is None:
                raise RuntimeError("no live session is running")
            if self._state.session_id != session_id:
                raise ValueError("session_id does not match active session")
            runtime = self._runtime

        final = runtime.stop()
        ended_at = _utc_now()
        self.audit.finish(
            session_id,
            final.model_dump(mode="json"),
            status=status.value,
        )

        with self._lock:
            assert self._state is not None
            self._state.status = status
            self._state.ended_at = ended_at
            self._runtime = None
            return final
