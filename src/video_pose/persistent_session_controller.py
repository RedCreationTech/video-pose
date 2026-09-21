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
from .runtime_fingerprint import build_runtime_fingerprint
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
from .violation_review import ViolationReviewRequest


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PersistentLiveSessionController:
    """Manage sessions without reconnecting cameras or reloading models."""

    def __init__(
        self,
        config: LoadedAnalysisConfig,
        *,
        hub: PersistentCameraHub,
        audit_root: str | Path,
        model_pool: PersistentModelPool | None = None,
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
        if self.model_pool is not None:
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
            if (
                self.model_pool is not None
                and not self.model_pool.loaded
            ):
                raise RuntimeError("persistent model pool is not loaded")
            if (
                self._state is not None
                and self._state.status == ManagedSessionStatus.RUNNING
            ):
                raise RuntimeError("a live session is already running")

            session_id = request.session_id or str(uuid.uuid4())
            runtime_kwargs: dict[str, Any] = {
                "hub": self.hub,
                "processing_queue_size": self.processing_queue_size,
                "session_id": session_id,
            }
            if self.model_pool is not None:
                runtime_kwargs["model_pool"] = self.model_pool
            runtime = self.runtime_factory(
                self.config,
                **runtime_kwargs,
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
            fingerprint = build_runtime_fingerprint(
                self.config,
                self.hub.manifest,
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
                **fingerprint.model_dump(mode="python"),
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

    def current_evaluation(self) -> dict[str, Any] | None:
        with self._lock:
            runtime = self._runtime
        if runtime is None:
            return None
        result = runtime.rule_session.current_result()
        return (
            result.model_dump(mode="json")
            if result is not None
            else None
        )

    def health_snapshot(self):
        return self.hub.health_snapshot()

    def camera_catalog(self) -> list[dict[str, Any]]:
        return self.hub.camera_catalog()

    def camera_snapshot(
        self,
        camera_id: str,
        *,
        quality: int = 80,
    ):
        return self.hub.snapshot_jpeg(
            camera_id,
            quality=quality,
        )

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

    def list_pending_reviews(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.repository is None:
            return []
        method = getattr(self.repository, "list_pending_reviews", None)
        if not callable(method):
            return []
        reviews = method(limit)
        evidence_cache: dict[str, list[dict[str, Any]]] = {}
        list_evidence = getattr(self.hub, "list_evidence", None)

        output: list[dict[str, Any]] = []
        for review in reviews:
            item = dict(review)
            session_id = str(item.get("session_id", ""))
            if callable(list_evidence) and session_id:
                if session_id not in evidence_cache:
                    evidence_cache[session_id] = list_evidence(session_id)
                item["evidence"] = [
                    manifest
                    for manifest in evidence_cache[session_id]
                    if (
                        manifest.get("rule_id") == item.get("rule_id")
                        and manifest.get("step_code")
                        == item.get("step_code")
                        and manifest.get("event_id")
                        == item.get("event_id")
                    )
                ]
            else:
                item["evidence"] = []
            output.append(item)
        return output

    def review_violation(
        self,
        session_id: str,
        violation_id: int,
        review: ViolationReviewRequest,
        *,
        reviewer: str,
    ) -> dict[str, Any]:
        if self.repository is None:
            raise RuntimeError("review repository is unavailable")

        session_payload = self.repository.get_session(session_id)
        if session_payload is None:
            raise LookupError("session not found")
        violation = next(
            (
                item
                for item in session_payload.get("violations", [])
                if int(item.get("id", -1)) == violation_id
            ),
            None,
        )
        if violation is None:
            raise LookupError("violation not found")

        reviewed_at = _utc_now()
        audit_payload = {
            "session_id": session_id,
            "violation_id": violation_id,
            "rule_id": str(violation.get("rule_id", "")),
            "step_code": str(violation.get("step_code", "")),
            "event_id": str(violation.get("event_id", "")),
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "review": review.model_dump(mode="json"),
        }
        self.audit.append_review(session_id, audit_payload)
        mark_evidence = getattr(
            self.hub,
            "mark_evidence_reviewed",
            None,
        )
        if callable(mark_evidence):
            mark_evidence(
                session_id,
                rule_id=audit_payload["rule_id"],
                step_code=audit_payload["step_code"],
                event_id=audit_payload["event_id"],
                status=review.decision.value,
                reviewed_at=reviewed_at,
            )

        method = getattr(self.repository, "review_violation", None)
        if not callable(method):
            return {
                **audit_payload,
                "persistence_status": "AUDIT_ONLY",
            }

        result = method(
            session_id,
            violation_id,
            review,
            reviewer=reviewer,
            reviewed_at=datetime.fromisoformat(reviewed_at),
        )
        if result is None:
            return {
                **audit_payload,
                "persistence_status": "DEGRADED",
            }
        return result

    def list_evidence(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        method = getattr(self.hub, "list_evidence", None)
        if not callable(method):
            return []
        return method(session_id)

    def evidence_manifest(
        self,
        session_id: str,
        evidence_id: str,
    ) -> dict[str, Any] | None:
        method = getattr(self.hub, "evidence_manifest", None)
        if not callable(method):
            return None
        return method(session_id, evidence_id)

    def evidence_file(
        self,
        session_id: str,
        evidence_id: str,
        camera_id: str,
        filename: str,
    ) -> bytes:
        method = getattr(self.hub, "evidence_file", None)
        if not callable(method):
            raise LookupError("evidence service is unavailable")
        return method(
            session_id,
            evidence_id,
            camera_id,
            filename,
        )

    def _handle_update(self, update: LiveAnalysisUpdate) -> None:
        with self._lock:
            state = self._state
            callback = self._event_callback
        if state is None:
            return

        payload = live_update_payload(update)
        self.audit.append_payload(state.session_id, payload)
        schedule_evidence = getattr(
            self.hub,
            "schedule_evidence",
            None,
        )
        if callable(schedule_evidence):
            timestamp_ms = update.trace.frame_set.reference_timestamp_ms
            for rule_update in update.rule_updates:
                for violation in rule_update.new_violations:
                    evidence_id = schedule_evidence(
                        state.session_id,
                        violation.model_dump(mode="json"),
                        timestamp_ms=timestamp_ms,
                    )
                    if evidence_id is not None:
                        self.audit.append_payload(
                            state.session_id,
                            {
                                "evidence_scheduled": {
                                    "evidence_id": evidence_id,
                                    "rule_id": violation.rule_id,
                                    "step": violation.step,
                                    "event_id": violation.event_id,
                                }
                            },
                        )
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
        latest_frame_set_method = getattr(
            self.hub,
            "latest_frame_set",
            None,
        )
        latest_frame_set = (
            latest_frame_set_method()
            if callable(latest_frame_set_method)
            else None
        )
        final_timestamp_ms = (
            latest_frame_set.reference_timestamp_ms
            if latest_frame_set is not None
            else 0.0
        )
        schedule_evidence = getattr(
            self.hub,
            "schedule_evidence",
            None,
        )
        if callable(schedule_evidence):
            for violation in final.new_violations:
                schedule_evidence(
                    session_id,
                    violation.model_dump(mode="json"),
                    timestamp_ms=final_timestamp_ms,
                )
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
