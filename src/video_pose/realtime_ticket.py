from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from .auth import AuthenticationError, AuthPrincipal


class RealtimeTicketResponse(BaseModel):
    ticket: str
    expires_at: str
    expires_in_seconds: int


@dataclass(slots=True)
class _TicketRecord:
    principal: AuthPrincipal
    expires_at_monotonic: float


class RealtimeTicketManager:
    """Issue one-time short-lived WebSocket tickets."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 30,
        max_outstanding: int = 1024,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be >= 1")
        if max_outstanding < 1:
            raise ValueError("max_outstanding must be >= 1")
        self.ttl_seconds = ttl_seconds
        self.max_outstanding = max_outstanding
        self._lock = threading.Lock()
        self._tickets: dict[str, _TicketRecord] = {}

    def issue(
        self,
        principal: AuthPrincipal,
    ) -> RealtimeTicketResponse:
        raw = secrets.token_urlsafe(32)
        digest = self._digest(raw)
        now_monotonic = time.monotonic()
        expires_monotonic = (
            now_monotonic + self.ttl_seconds
        )
        with self._lock:
            self._cleanup_locked(now_monotonic)
            while len(self._tickets) >= self.max_outstanding:
                oldest = next(iter(self._tickets))
                self._tickets.pop(oldest, None)
            self._tickets[digest] = _TicketRecord(
                principal=principal.model_copy(deep=True),
                expires_at_monotonic=expires_monotonic,
            )

        expires_at = (
            datetime.now(UTC)
            + timedelta(seconds=self.ttl_seconds)
        ).isoformat()
        return RealtimeTicketResponse(
            ticket=raw,
            expires_at=expires_at,
            expires_in_seconds=self.ttl_seconds,
        )

    def consume(self, ticket: str | None) -> AuthPrincipal:
        if not ticket:
            raise AuthenticationError(
                "missing realtime ticket"
            )
        digest = self._digest(ticket)
        now = time.monotonic()
        with self._lock:
            self._cleanup_locked(now)
            record = self._tickets.pop(digest, None)
        if (
            record is None
            or record.expires_at_monotonic <= now
        ):
            raise AuthenticationError(
                "invalid or expired realtime ticket"
            )
        return record.principal.model_copy(deep=True)

    def outstanding(self) -> int:
        now = time.monotonic()
        with self._lock:
            self._cleanup_locked(now)
            return len(self._tickets)

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            digest
            for digest, record in self._tickets.items()
            if record.expires_at_monotonic <= now
        ]
        for digest in expired:
            self._tickets.pop(digest, None)

    @staticmethod
    def _digest(ticket: str) -> str:
        return hashlib.sha256(
            ticket.encode("utf-8")
        ).hexdigest()
