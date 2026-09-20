from __future__ import annotations

from typing import Protocol

from .contracts import ActionEvent
from .observations import Observation


class IncrementalActionRecognizer(Protocol):
    def ingest(self, observations: list[Observation]) -> list[ActionEvent]: ...


class CompositeActionRecognizer:
    """Combine explainable action recognizers behind one ordered event stream."""

    def __init__(self, recognizers: list[IncrementalActionRecognizer]) -> None:
        self.recognizers = recognizers
        self._sequence = 0

    def ingest(self, observations: list[Observation]) -> list[ActionEvent]:
        events: list[ActionEvent] = []
        for recognizer in self.recognizers:
            events.extend(recognizer.ingest(observations))

        ordered = sorted(
            events,
            key=lambda event: (
                event.started_at_ms,
                event.ended_at_ms or event.started_at_ms,
                event.action.value,
                event.event_id,
            ),
        )
        output: list[ActionEvent] = []
        for event in ordered:
            self._sequence += 1
            output.append(
                event.model_copy(
                    update={
                        "event_id": f"action-{self._sequence:06d}",
                        "sequence": self._sequence,
                    }
                )
            )
        return output
