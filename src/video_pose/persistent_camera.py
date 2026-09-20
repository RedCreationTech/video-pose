from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any

from .camera_preview import EncodedSnapshot, encode_jpeg
from .live_capture_factory import build_live_camera_factory
from .async_evidence import AsyncLiveEvidenceRecorder
from .live_evidence import LiveEvidenceBuffer, OpenCVJPEGEncoder
from .live_gateway import ThreadedLiveGateway
from .live_health import LiveHealthRegistry, LiveHealthSnapshot
from .live_video import LiveFrameSynchronizer, MemoryFrameStore
from .runtime_config import LoadedAnalysisConfig
from .video_manifest import ReplayManifest, load_manifest
from .video_replay import SynchronizedFrameSet


class PersistentCameraHub:
    """Own camera connections for the whole service lifetime."""

    def __init__(
        self,
        *,
        manifest: ReplayManifest,
        frame_store: MemoryFrameStore,
        health: LiveHealthRegistry,
        gateway: ThreadedLiveGateway,
        evidence: AsyncLiveEvidenceRecorder | None = None,
    ) -> None:
        self.manifest = manifest
        self.frame_store = frame_store
        self.health = health
        self.gateway = gateway
        self.evidence = evidence
        self._lock = threading.RLock()
        self._subscribers: dict[
            str,
            Callable[[SynchronizedFrameSet], None],
        ] = {}
        self._running = False
        self._latest_frame_set: SynchronizedFrameSet | None = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        try:
            if self.evidence is not None:
                self.evidence.start()
            self.gateway.start(self._publish)
        except Exception:
            if self.evidence is not None:
                self.evidence.stop()
            with self._lock:
                self._running = False
            raise

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        self.gateway.stop()
        if self.evidence is not None:
            self.evidence.stop()

    def subscribe(
        self,
        callback: Callable[[SynchronizedFrameSet], None],
    ) -> str:
        token = str(uuid.uuid4())
        with self._lock:
            self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: str) -> None:
        with self._lock:
            self._subscribers.pop(token, None)

    def health_snapshot(self) -> LiveHealthSnapshot:
        return self.health.snapshot()

    def camera_catalog(self) -> list[dict[str, Any]]:
        health_by_id = {
            item.camera_id: item
            for item in self.health.snapshot().cameras
        }
        with self._lock:
            latest = self._latest_frame_set

        output: list[dict[str, Any]] = []
        for camera in self.manifest.cameras:
            health = health_by_id.get(camera.camera_id)
            output.append(
                {
                    "camera_id": camera.camera_id,
                    "position": camera.position.value,
                    "codec": camera.codec,
                    "enabled": camera.enabled,
                    "state": (
                        health.state.value
                        if health is not None
                        else "UNKNOWN"
                    ),
                    "fps": (
                        health.fps_estimate
                        if health is not None
                        else 0.0
                    ),
                    "reconnect_total": (
                        health.reconnect_total
                        if health is not None
                        else 0
                    ),
                    "snapshot_available": (
                        latest is not None
                        and any(
                            ref.camera_id == camera.camera_id
                            for ref in latest.frames.values()
                        )
                    ),
                }
            )
        return output

    def snapshot_jpeg(
        self,
        camera_id: str,
        *,
        quality: int = 80,
    ) -> EncodedSnapshot:
        with self._lock:
            latest = self._latest_frame_set
        if latest is None:
            raise LookupError("no synchronized camera frame is available yet")

        frame_ref = next(
            (
                ref
                for ref in latest.frames.values()
                if ref.camera_id == camera_id
            ),
            None,
        )
        if frame_ref is None:
            raise KeyError(
                f"camera is not present in latest frame set: {camera_id}"
            )

        frame = self.frame_store.load(frame_ref)
        return encode_jpeg(
            frame.image,
            timestamp_ms=frame_ref.normalized_timestamp_ms,
            quality=quality,
        )

    def schedule_evidence(
        self,
        session_id: str,
        violation: dict[str, Any],
        *,
        timestamp_ms: float,
    ) -> str | None:
        if self.evidence is None:
            return None
        return self.evidence.schedule(
            session_id,
            violation,
            timestamp_ms=timestamp_ms,
        )

    def list_evidence(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        if self.evidence is None:
            return []
        return [
            manifest.model_dump(mode="json")
            for manifest in self.evidence.list_session(session_id)
        ]

    def evidence_manifest(
        self,
        session_id: str,
        evidence_id: str,
    ) -> dict[str, Any] | None:
        if self.evidence is None:
            return None
        manifest = self.evidence.get_manifest(session_id, evidence_id)
        return (
            manifest.model_dump(mode="json")
            if manifest is not None
            else None
        )

    def evidence_file(
        self,
        session_id: str,
        evidence_id: str,
        camera_id: str,
        filename: str,
    ) -> bytes:
        if self.evidence is None:
            raise LookupError("live evidence is disabled")
        return self.evidence.read_file(
            session_id,
            evidence_id,
            camera_id,
            filename,
        )

    def latest_frame_set(self) -> SynchronizedFrameSet | None:
        with self._lock:
            return self._latest_frame_set

    def _publish(self, frame_set: SynchronizedFrameSet) -> None:
        self.health.frame_set_received()
        if self.evidence is not None:
            try:
                self.evidence.submit(frame_set, self.frame_store)
            except Exception:
                self.health.processing_error()
        with self._lock:
            self._latest_frame_set = frame_set
            callbacks = list(self._subscribers.values())
        for callback in callbacks:
            try:
                callback(frame_set)
            except Exception:
                self.health.processing_error()


def build_persistent_camera_hub(
    config: LoadedAnalysisConfig,
    *,
    processing_queue_size: int = 2,
    max_frame_store: int = 64,
) -> PersistentCameraHub:
    manifest = load_manifest(config.resolve(config.config.manifest))
    frame_store = MemoryFrameStore(max_frames=max_frame_store)
    health = LiveHealthRegistry(
        [
            camera.camera_id
            for camera in manifest.cameras
            if camera.enabled
        ],
        queue_capacity=processing_queue_size,
    )
    synchronizer = LiveFrameSynchronizer(
        manifest,
        frame_store,
    )
    gateway = ThreadedLiveGateway(
        manifest,
        synchronizer,
        health=health,
        camera_factory=build_live_camera_factory(
            manifest,
            config.config.live,
        ),
    )
    evidence = None
    if config.config.evidence.enabled:
        evidence = AsyncLiveEvidenceRecorder(
            LiveEvidenceBuffer(
                root=config.resolve(config.config.evidence.root),
                encoder=OpenCVJPEGEncoder(
                    quality=config.config.evidence.jpeg_quality
                ),
                camera_ids=[
                    camera.camera_id
                    for camera in manifest.cameras
                    if camera.enabled
                ],
                pre_roll_ms=config.config.evidence.pre_roll_ms,
                post_roll_ms=config.config.evidence.post_roll_ms,
                sample_interval_ms=config.config.evidence.sample_interval_ms,
                max_pending=config.config.evidence.max_pending,
            ),
            queue_size=config.config.evidence.worker_queue_size,
        )
    return PersistentCameraHub(
        manifest=manifest,
        frame_store=frame_store,
        health=health,
        gateway=gateway,
        evidence=evidence,
    )
