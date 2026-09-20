from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from .live_payload import live_update_payload
from .live_runtime import LiveAnalysisUpdate


@dataclass(frozen=True, slots=True)
class LiveEventEnvelope:
    sequence: int
    payload: dict[str, Any]


class LiveEventBroker:
    """Thread-safe latest-event broker for WebSocket delivery."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._sequence = 0
        self._latest: LiveEventEnvelope | None = None

    def publish(self, update: LiveAnalysisUpdate) -> LiveEventEnvelope:
        with self._condition:
            self._sequence += 1
            envelope = LiveEventEnvelope(
                sequence=self._sequence,
                payload=live_update_payload(update),
            )
            self._latest = envelope
            self._condition.notify_all()
            return envelope

    def latest(self) -> LiveEventEnvelope | None:
        with self._condition:
            return self._latest

    def wait_next(
        self,
        after_sequence: int,
        *,
        timeout_s: float = 5.0,
    ) -> LiveEventEnvelope | None:
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self._latest is not None
                    and self._latest.sequence > after_sequence
                ),
                timeout=timeout_s,
            )
            if (
                self._latest is None
                or self._latest.sequence <= after_sequence
            ):
                return None
            return self._latest
