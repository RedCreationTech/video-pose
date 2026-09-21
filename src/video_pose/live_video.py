from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

from .frames import DecodedFrame
from .live_health import LiveHealthRegistry
from .video_manifest import CameraPosition, ReplayManifest
from .video_replay import FrameRef, SynchronizedFrameSet


class MemoryFrameStore:
    """Bounded thread-safe in-memory FrameLoader for live camera pixels."""

    def __init__(self, max_frames: int = 1024) -> None:
        if max_frames < 4:
            raise ValueError("max_frames must be >= 4")
        self.max_frames = max_frames
        self._frames: dict[str, Any] = {}
        self._order: deque[str] = deque()
        self._lock = threading.Lock()

    def put(
        self,
        *,
        camera_id: str,
        sequence: int,
        image: Any,
    ) -> str:
        uri = f"memory://{camera_id}/{sequence}"
        with self._lock:
            self._frames[uri] = image
            self._order.append(uri)
            while len(self._order) > self.max_frames:
                expired = self._order.popleft()
                self._frames.pop(expired, None)
        return uri

    def load(self, ref: FrameRef) -> DecodedFrame:
        with self._lock:
            if ref.uri not in self._frames:
                raise KeyError(f"live frame expired or missing: {ref.uri}")
            image = self._frames[ref.uri]
        return DecodedFrame(ref=ref, image=image)


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
        health: LiveHealthRegistry | None = None,
    ) -> None:
        if max_buffer_frames < 1:
            raise ValueError("max_buffer_frames must be >= 1")
        self.manifest = manifest
        self.frame_store = frame_store
        self.reference_position = reference_position
        self.max_buffer_frames = max_buffer_frames
        self.health = health
        if self.health is not None:
            self.health.enable_sync()
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
        self._sequences = {
            camera_id: 0 for camera_id in self._camera_by_id
        }
        self._last_emitted_reference_ms = -1.0
        self._lock = threading.Lock()

    def push(
        self,
        *,
        camera_id: str,
        source_timestamp_ms: float,
        image: Any,
    ) -> SynchronizedFrameSet | None:
        with self._lock:
            return self._push_locked(
                camera_id=camera_id,
                source_timestamp_ms=source_timestamp_ms,
                image=image,
            )

    def _push_locked(
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
        if self.health is not None:
            self.health.sync_reference_frame()
        if packet.normalized_timestamp_ms <= self._last_emitted_reference_ms:
            if self.health is not None:
                self.health.sync_miss("stale_reference")
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
                if self.health is not None:
                    self.health.sync_miss("missing_buffer")
                return None
            buffer = self._buffers[camera.camera_id]
            if not buffer:
                if self.health is not None:
                    self.health.sync_miss("missing_buffer")
                return None
            packet = min(
                buffer,
                key=lambda item: abs(
                    item.normalized_timestamp_ms - target
                ),
            )
            if abs(packet.normalized_timestamp_ms - target) > tolerance:
                if self.health is not None:
                    self.health.sync_miss("tolerance")
                return None
            selected[position] = packet

        values = [
            packet.normalized_timestamp_ms
            for packet in selected.values()
        ]
        skew_ms = max(values) - min(values)
        if self.health is not None:
            self.health.sync_emitted(
                reference_timestamp_ms=target,
                skew_ms=skew_ms,
                camera_offsets_ms={
                    packet.camera_id: (
                        packet.normalized_timestamp_ms - target
                    )
                    for packet in selected.values()
                },
            )
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
            skew_ms=skew_ms,
        )
