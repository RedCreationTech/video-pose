from __future__ import annotations

import threading
import uuid
from collections.abc import Callable

from .live_capture_factory import build_live_camera_factory
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
    ) -> None:
        self.manifest = manifest
        self.frame_store = frame_store
        self.health = health
        self.gateway = gateway
        self._lock = threading.RLock()
        self._subscribers: dict[
            str,
            Callable[[SynchronizedFrameSet], None],
        ] = {}
        self._running = False

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
            self.gateway.start(self._publish)
        except Exception:
            with self._lock:
                self._running = False
            raise

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        self.gateway.stop()

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

    def _publish(self, frame_set: SynchronizedFrameSet) -> None:
        self.health.frame_set_received()
        with self._lock:
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
    max_frame_store: int = 1024,
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
    return PersistentCameraHub(
        manifest=manifest,
        frame_store=frame_store,
        health=health,
        gateway=gateway,
    )
