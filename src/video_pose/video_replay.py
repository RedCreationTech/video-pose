from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .probe import probe_frame_timestamps
from .sync import synchronize_timestamps
from .video_manifest import CameraPosition, ReplayManifest, load_manifest


class TimestampProvider(Protocol):
    def timestamps_ms(self, uri: str) -> Sequence[float]: ...


class FFprobeTimestampProvider:
    def timestamps_ms(self, uri: str) -> Sequence[float]:
        return probe_frame_timestamps(uri)


@dataclass(frozen=True, slots=True)
class FrameRef:
    camera_id: str
    position: CameraPosition
    uri: str
    source_timestamp_ms: float
    normalized_timestamp_ms: float


@dataclass(frozen=True, slots=True)
class SynchronizedFrameSet:
    reference_timestamp_ms: float
    frames: dict[CameraPosition, FrameRef]
    skew_ms: float


class ReplayPlanner:
    """Build synchronized four-view frame references without decoding pixels."""

    def __init__(
        self,
        manifest: ReplayManifest,
        *,
        manifest_dir: Path,
        timestamp_provider: TimestampProvider,
    ) -> None:
        self.manifest = manifest
        self.manifest_dir = manifest_dir
        self.timestamp_provider = timestamp_provider

    @classmethod
    def from_manifest_file(
        cls,
        path: str | Path,
        timestamp_provider: TimestampProvider | None = None,
    ) -> ReplayPlanner:
        manifest_path = Path(path)
        return cls(
            load_manifest(manifest_path),
            manifest_dir=manifest_path.parent,
            timestamp_provider=timestamp_provider or FFprobeTimestampProvider(),
        )

    def plan(self) -> list[SynchronizedFrameSet]:
        normalized_streams: dict[CameraPosition, list[float]] = {}
        camera_by_position = {
            camera.position: camera
            for camera in self.manifest.cameras
            if camera.enabled
        }

        for position, camera in camera_by_position.items():
            uri = self._resolve_uri(camera.uri)
            source = self.timestamp_provider.timestamps_ms(uri)
            normalized_streams[position] = [
                timestamp + camera.clock_offset_ms for timestamp in source
            ]

        synchronized = synchronize_timestamps(
            normalized_streams,
            tolerance_ms=self.manifest.sync_tolerance_ms,
        )

        output: list[SynchronizedFrameSet] = []
        for frame in synchronized:
            refs: dict[CameraPosition, FrameRef] = {}
            for position, normalized_timestamp in frame.timestamps_ms.items():
                camera = camera_by_position[position]
                refs[position] = FrameRef(
                    camera_id=camera.camera_id,
                    position=position,
                    uri=self._resolve_uri(camera.uri),
                    source_timestamp_ms=(
                        normalized_timestamp - camera.clock_offset_ms
                    ),
                    normalized_timestamp_ms=normalized_timestamp,
                )
            output.append(
                SynchronizedFrameSet(
                    reference_timestamp_ms=frame.reference_timestamp_ms,
                    frames=refs,
                    skew_ms=frame.skew_ms,
                )
            )
        return output

    def _resolve_uri(self, uri: str) -> str:
        if "://" in uri:
            return uri
        path = Path(uri)
        if path.is_absolute():
            return str(path)
        return str((self.manifest_dir / path).resolve())
