from __future__ import annotations

from typing import Any, Protocol

from .session_audit import SessionAuditMetadata


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
