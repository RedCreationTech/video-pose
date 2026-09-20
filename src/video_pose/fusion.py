from __future__ import annotations

from collections.abc import Iterable

from .observations import Observation


def _semantic_key(observation: Observation) -> tuple[object, ...]:
    return (
        observation.type,
        observation.entity_id,
        observation.entity_class,
        observation.relation,
        observation.target_id,
        observation.zone,
    )


def fuse_observations(observations: Iterable[Observation]) -> list[Observation]:
    """Keep the strongest multi-view evidence for each semantic fact.

    This is intentionally simple for the MVP. Later versions can replace it with
    geometry-aware fusion without changing the Observation contract.
    """

    best: dict[tuple[object, ...], Observation] = {}
    for observation in observations:
        key = _semantic_key(observation)
        current = best.get(key)
        if current is None or observation.confidence > current.confidence:
            best[key] = observation
    return sorted(
        best.values(),
        key=lambda item: (
            item.timestamp_ms,
            item.entity_id,
            item.type.value,
            item.camera_id,
        ),
    )
