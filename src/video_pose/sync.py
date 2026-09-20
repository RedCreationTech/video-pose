from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .video_manifest import CameraPosition


@dataclass(frozen=True, slots=True)
class SyncedFrame:
    reference_timestamp_ms: float
    timestamps_ms: dict[CameraPosition, float]
    skew_ms: float


def nearest_timestamp(values: Sequence[float], target: float) -> float | None:
    if not values:
        return None
    return min(values, key=lambda value: abs(value - target))


def synchronize_timestamps(
    streams: Mapping[CameraPosition, Sequence[float]],
    tolerance_ms: float,
    reference: CameraPosition = CameraPosition.FRONT,
) -> list[SyncedFrame]:
    if tolerance_ms <= 0:
        raise ValueError("tolerance_ms must be positive")
    if reference not in streams:
        raise ValueError(f"reference stream {reference.value} is missing")

    required = set(CameraPosition)
    missing = required - set(streams)
    if missing:
        names = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"missing camera streams: {names}")

    output: list[SyncedFrame] = []
    for reference_ts in streams[reference]:
        selected: dict[CameraPosition, float] = {reference: reference_ts}
        valid = True
        for position in CameraPosition:
            if position == reference:
                continue
            candidate = nearest_timestamp(streams[position], reference_ts)
            if candidate is None or abs(candidate - reference_ts) > tolerance_ms:
                valid = False
                break
            selected[position] = candidate
        if not valid:
            continue
        values = list(selected.values())
        output.append(
            SyncedFrame(
                reference_timestamp_ms=reference_ts,
                timestamps_ms=selected,
                skew_ms=max(values) - min(values),
            )
        )
    return output
