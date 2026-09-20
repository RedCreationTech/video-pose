from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .frames import DecodedFrame
from .video_manifest import CameraPosition, ReplayManifest
from .video_replay import FrameRef, SynchronizedFrameSet


class MemoryFrameStore:
    """Bounded in-memory frame store implementing the FrameLoader contract."""

    def __init__(self, max_frames: int = 1024) -> None:
        if max_frames < 4:
            raise ValueError("max_frames must be >= 4")
        self.max_frames = max_frames
        self._frames: dict[str, Any] = {}
        self._order: deque[str] = deque()

    def put(
        self,
        *,
        camera_id: str,
        sequence: int,
        image: Any,
    ) -> str:
        uri = f"memory://{camera_id}/{sequence}"
        self._frames[uri] = image
        self._order.append(uri)
        while len(self._order) > self.max_frames:
            expired = self._order.popleft()
            self._frames.pop(expired, None)
        return uri

    def load(self, ref: FrameRef) -> DecodedFrame:
        if ref.uri not in self._frames:
            raise KeyError(f"live frame expired or missing: {ref.uri}")
        return DecodedFrame(ref=ref, image=self._frames[ref.uri])


@dataclass(frozen=True, slots=True)
class LiveFramePacket:
    camera_id: str
    position: CameraPosition
    uri: str
    source_timestamp_ms: float
    normalized_timestamp_ms: float


class LiveFrameSynchronizer:
    """Synchronize incoming camera frames onto the shared four-view contract."""

    def __init__(
        self,
        manifest: ReplayManifest,
        frame_store: MemoryFrameStore,
        *,
        reference_position: CameraPosition = CameraPosition.FRONT,
        max_buffer_frames: int = 120,
    ) -> None:
        if max_buffer_frames < 1:
            raise ValueError("max_buffer_frames must be >= 1")
        self.manifest = manifest
        self.frame_store = frame_store
        self.reference_position = reference_position
        self.max_buffer_frames = max_buffer_frames
        self._camera_by_id = {
            camera.camera_id: camera
            for camera in manifest.cameras
            if camera.enabled
        }
        self._camera_by_position = {
            camera.position: camera
            for camera in manifest.cameras
            if camera.enabled
        }
        self._buffers: dict[str, deque[LiveFramePacket]] = {
            camera_id: deque(maxlen=max_buffer_frames)
            for camera_id in self._camera_by_id
        }
        self._sequences: dict[str, int] = {
            camera_id: 0 for camera_id in self._camera_by_id
        }
        self._last_emitted_reference_ms = -1.0

    def push(
        self,
        *,
        camera_id: str,
        source_timestamp_ms: float,
        image: Any,
    ) -> SynchronizedFrameSet | None:
        camera = self._camera_by_id.get(camera_id)
        if camera is None:
            raise KeyError(f"unknown live camera: {camera_id}")

        self._sequences[camera_id] += 1
        sequence = self._sequences[camera_id]
        uri = self.frame_store.put(
            camera_id=camera_id,
            sequence=sequence,
            image=image,
        )
        packet = LiveFramePacket(
            camera_id=camera_id,
            position=camera.position,
            uri=uri,
            source_timestamp_ms=source_timestamp_ms,
            normalized_timestamp_ms=(
                source_timestamp_ms + camera.clock_offset_ms
            ),
        )
        self._buffers[camera_id].append(packet)

        if camera.position != self.reference_position:
            return None
        if packet.normalized_timestamp_ms <= self._last_emitted_reference_ms:
            return None

        synchronized = self._match(packet)
        if synchronized is not None:
            self._last_emitted_reference_ms = packet.normalized_timestamp_ms
        return synchronized

    def _match(
        self,
        reference_packet: LiveFramePacket,
    ) -> SynchronizedFrameSet | None:
        selected: dict[CameraPosition, LiveFramePacket] = {}
        target = reference_packet.normalized_timestamp_ms
        tolerance = self.manifest.sync_tolerance_ms

        for position in CameraPosition:
            camera = self._camera_by_position.get(position)
            if camera is None:
                return None
            buffer = self._buffers[camera.camera_id]
            if not buffer:
                return None
            packet = min(
                buffer,
                key=lambda item: abs(
                    item.normalized_timestamp_ms - target
                ),
            )
            if abs(packet.normalized_timestamp_ms - target) > tolerance:
                return None
            selected[position] = packet

        values = [
            packet.normalized_timestamp_ms
            for packet in selected.values()
        ]
        return SynchronizedFrameSet(
            reference_timestamp_ms=target,
            frames={
                position: FrameRef(
                    camera_id=packet.camera_id,
                    position=position,
                    uri=packet.uri,
                    source_timestamp_ms=packet.source_timestamp_ms,
                    normalized_timestamp_ms=packet.normalized_timestamp_ms,
                )
                for position, packet in selected.items()
            },
            skew_ms=max(values) - min(values),
        )
