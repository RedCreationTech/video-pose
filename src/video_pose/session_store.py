from __future__ import annotations

from typing import Any, Protocol

from .session_audit import SessionAuditMetadata
from .violation_review import ViolationReviewRequest


class SessionStore(Protocol):
    """Queryable persistence contract beside the immutable JSONL audit."""

    def create_schema(self) -> None: ...

    def start_session(self, metadata: SessionAuditMetadata) -> None: ...

    def record_update(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None: ...

    def finalize(
        self,
        session_id: str,
        final_payload: dict[str, Any],
        *,
        status: str,
    ) -> None: ...

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]: ...

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None: ...

    def list_pending_reviews(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def review_violation(
        self,
        session_id: str,
        violation_id: int,
        review: ViolationReviewRequest,
        *,
        reviewer: str,
        reviewed_at: Any | None = None,
    ) -> dict[str, Any] | None: ...

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
    ) -> dict[str, Any] | None: ...
