from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .live_payload import live_update_payload
from .live_runtime import LiveAnalysisUpdate
from .model_pool import PersistentModelPool
from .persistent_camera import PersistentCameraHub
from .realtime_rules import RuleSessionUpdate
from .runtime_config import LoadedAnalysisConfig
from .session_audit import SessionAuditMetadata, SessionAuditWriter
from .session_controller import (
    ManagedSessionState,
    ManagedSessionStatus,
    SessionStartRequest,
)
from .session_runtime import (
    SessionAnalysisRuntime,
    build_session_analysis_runtime,
)
from .session_store import SessionStore


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PersistentLiveSessionController:
    """Manage sessions without reconnecting cameras or reloading models."""

    def __init__(
        self,
        config: LoadedAnalysisConfig,
        *,
        hub: PersistentCameraHub,
        model_pool: PersistentModelPool,
        audit_root: str | Path,
        processing_queue_size: int = 2,
        runtime_factory: Callable[
            ...,
            SessionAnalysisRuntime,
        ] = build_session_analysis_runtime,
        repository: SessionStore | None = None,
    ) -> None:
        self.config = config
        self.hub = hub
        self.model_pool = model_pool
        self.audit = SessionAuditWriter(audit_root)
        self.processing_queue_size = processing_queue_size
        self.runtime_factory = runtime_factory
        self.repository = repository
        self._lock = threading.RLock()
        self._runtime: SessionAnalysisRuntime | None = None
        self._state: ManagedSessionState | None = None
        self._event_callback: Callable[[LiveAnalysisUpdate], Any] | None = None

    def start_hub(self) -> None:
        self.model_pool.load()
        self.hub.start()

    def shutdown(self) -> None:
        current = self.current()
        if (
            current is not None
            and current.status == ManagedSessionStatus.RUNNING
        ):
            self.abort(current.session_id)
        self.hub.stop()

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
            if not self.hub.running:
                raise RuntimeError("persistent camera hub is not running")
            if not self.model_pool.loaded:
                raise RuntimeError("persistent model pool is not loaded")
            if (
                self._state is not None
                and self._state.status == ManagedSessionStatus.RUNNING
            ):
                raise RuntimeError("a live session is already running")

            session_id = request.session_id or str(uuid.uuid4())
            runtime = self.runtime_factory(
                self.config,
                hub=self.hub,
                model_pool=self.model_pool,
                processing_queue_size=self.processing_queue_size,
                session_id=session_id,
            )
            rule_set = runtime.rule_session.engine.rule_set
            started_at = _utc_now()
            state = ManagedSessionState(
                session_id=session_id,
                operator_id=request.operator_id,
                operation=rule_set.operation,
                workstation_id=self.hub.manifest.workstation_id,
                status=ManagedSessionStatus.RUNNING,
                started_at=started_at,
            )
            metadata = SessionAuditMetadata(
                session_id=session_id,
                operator_id=request.operator_id,
                operation=rule_set.operation,
                workstation_id=self.hub.manifest.workstation_id,
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
            if self.repository is not None:
                self.repository.start_session(metadata)
            self._runtime = runtime
            self._state = state

            try:
                runtime.start(self._handle_update)
            except Exception:
                self._runtime = None
                self._state = None
                final_payload = {"error": "session runtime start failed"}
                self.audit.finish(
                    session_id,
                    final_payload,
                    status=ManagedSessionStatus.ABORTED.value,
                )
                if self.repository is not None:
                    self.repository.finalize(
                        session_id,
                        final_payload,
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

    def health_snapshot(self):
        return self.hub.health_snapshot()

    def persistence_health(self) -> dict[str, Any]:
        if self.repository is None:
            return {
                "configured": False,
                "status": "DISABLED",
            }
        health_method = getattr(self.repository, "health", None)
        if callable(health_method):
            health = health_method()
            dump_method = getattr(health, "model_dump", None)
            payload = (
                dump_method(mode="json")
                if callable(dump_method)
                else health
            )
            return {
                "configured": True,
                **payload,
            }
        return {
            "configured": True,
            "status": "READY",
        }

    def list_sessions(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.repository is None:
            return []
        return self.repository.list_sessions(limit)

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        if self.repository is None:
            return None
        return self.repository.get_session(session_id)

    def _handle_update(self, update: LiveAnalysisUpdate) -> None:
        with self._lock:
            state = self._state
            callback = self._event_callback
        if state is None:
            return

        payload = live_update_payload(update)
        self.audit.append_payload(state.session_id, payload)
        if self.repository is not None:
            self.repository.record_update(state.session_id, payload)
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
        final_payload = final.model_dump(mode="json")
        self.audit.finish(
            session_id,
            final_payload,
            status=status.value,
        )
        if self.repository is not None:
            self.repository.finalize(
                session_id,
                final_payload,
                status=status.value,
            )

        with self._lock:
            assert self._state is not None
            self._state.status = status
            self._state.ended_at = ended_at
            self._runtime = None
            return final
