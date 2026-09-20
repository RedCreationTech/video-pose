from __future__ import annotations

from typing import Protocol

from .observations import Observation


class ObservationEnricher(Protocol):
    def enrich(self, observations: list[Observation]) -> list[Observation]: ...
