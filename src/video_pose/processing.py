from __future__ import annotations

from typing import Protocol

from .observations import Observation


class ObservationProcessor(Protocol):
    def process(self, observations: list[Observation]) -> list[Observation]: ...
