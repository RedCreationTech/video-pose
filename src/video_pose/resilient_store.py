from __future__ import annotations

import threading
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from .session_audit import SessionAuditMetadata
from .session_store import SessionStore
from .violation_review import ViolationReviewRequest


class PersistenceStatus(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"


class PersistenceHealth(BaseModel):
    status: PersistenceStatus
    write_errors_total: int = 0
    read_errors_total: int = 0
    last_error: str | None = None


class ResilientSessionStore:
    """Best-effort query store. JSONL audit remains the durable source."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store
        self._lock = threading.Lock()
        self._write_errors_total = 0
        self._read_errors_total = 0
        self._last_error: str | None = None
        self._status = PersistenceStatus.READY

    def create_schema(self) -> None:
        try:
            self.store.create_schema()
            self._mark_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def start_session(self, metadata: SessionAuditMetadata) -> None:
        try:
            self.store.start_session(metadata)
            self._mark_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def record_update(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            self.store.record_update(session_id, payload)
            self._mark_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def finalize(
        self,
        session_id: str,
        final_payload: dict[str, Any],
        *,
        status: str,
    ) -> None:
        try:
            self.store.finalize(
                session_id,
                final_payload,
                status=status,
            )
            self._mark_success()
        except Exception as exc:
            self._mark_write_error(exc)

    def list_sessions(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            result = self.store.list_sessions(limit)
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_read_error(exc)
            return []

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        try:
            result = self.store.get_session(session_id)
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_read_error(exc)
            return None

    def list_pending_reviews(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            result = self.store.list_pending_reviews(limit)
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_read_error(exc)
            return []

    def review_violation(
        self,
        session_id: str,
        violation_id: int,
        review: ViolationReviewRequest,
        *,
        reviewer: str,
        reviewed_at: Any | None = None,
    ) -> dict[str, Any] | None:
        try:
            result = self.store.review_violation(
                session_id,
                violation_id,
                review,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
            )
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_write_error(exc)
            return None

    def review_violation_by_identity(
        self,
        session_id: str,
        *,
        rule_id: str,
        step_code: str,
        event_id: str,
        review: ViolationReviewRequest,
        reviewer: str,
        reviewed_at: Any | None = None,
    ) -> dict[str, Any] | None:
        try:
            result = self.store.review_violation_by_identity(
                session_id,
                rule_id=rule_id,
                step_code=step_code,
                event_id=event_id,
                review=review,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
            )
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_write_error(exc)
            return None

    def probe(self) -> PersistenceHealth:
        try:
            self.store.list_sessions(1)
            self._mark_success()
        except Exception as exc:
            self._mark_read_error(exc)
        return self.health()

    def health(self) -> PersistenceHealth:
        with self._lock:
            return PersistenceHealth(
                status=self._status,
                write_errors_total=self._write_errors_total,
                read_errors_total=self._read_errors_total,
                last_error=self._last_error,
            )

    def _mark_success(self) -> None:
        with self._lock:
            self._status = PersistenceStatus.READY
            self._last_error = None

    def _mark_write_error(self, exc: Exception) -> None:
        with self._lock:
            self._status = PersistenceStatus.DEGRADED
            self._write_errors_total += 1
            self._last_error = str(exc)

    def _mark_read_error(self, exc: Exception) -> None:
        with self._lock:
            self._status = PersistenceStatus.DEGRADED
            self._read_errors_total += 1
            self._last_error = str(exc)
