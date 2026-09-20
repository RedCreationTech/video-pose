from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .live_gateway import ThreadedLiveGateway
from .live_health import LiveHealthRegistry, LiveHealthSnapshot
from .live_video import LiveFrameSynchronizer, MemoryFrameStore
from .pipeline import VideoPosePipeline
from .realtime_rules import RealtimeRuleSession, RuleSessionUpdate
from .runtime_builder import build_analysis_pipeline, build_rule_engine
from .runtime_config import LoadedAnalysisConfig
from .trace import FrameTrace
from .video_manifest import load_manifest
from .video_replay import SynchronizedFrameSet


@dataclass(frozen=True, slots=True)
class LiveAnalysisUpdate:
    trace: FrameTrace
    rule_updates: tuple[RuleSessionUpdate, ...]


class LiveAnalysisRuntime:
    """Decouple capture from inference with bounded drop-oldest backpressure."""

    def __init__(
        self,
        *,
        gateway: ThreadedLiveGateway,
        pipeline: VideoPosePipeline,
        rule_session: RealtimeRuleSession,
        health: LiveHealthRegistry,
        processing_queue_size: int = 2,
    ) -> None:
        if processing_queue_size < 1:
            raise ValueError("processing_queue_size must be >= 1")
        self.gateway = gateway
        self.pipeline = pipeline
        self.rule_session = rule_session
        self.health = health
        self._last_timestamp_ms = 0
        self._callback: Callable[[LiveAnalysisUpdate], None] | None = None
        self._queue: queue.Queue[SynchronizedFrameSet] = queue.Queue(
            maxsize=processing_queue_size
        )
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()

    def process_frame_set(
        self,
        frame_set: SynchronizedFrameSet,
    ) -> LiveAnalysisUpdate:
        trace = self.pipeline.process_with_trace([frame_set])[0]
        now_ms = round(frame_set.reference_timestamp_ms)
        self._last_timestamp_ms = max(self._last_timestamp_ms, now_ms)

        rule_updates: list[RuleSessionUpdate] = []
        if trace.actions:
            for action in trace.actions:
                rule_updates.append(self.rule_session.ingest(action))
        else:
            rule_updates.append(self.rule_session.tick(now_ms))

        return LiveAnalysisUpdate(
            trace=trace,
            rule_updates=tuple(rule_updates),
        )

    def enqueue_frame_set(
        self,
        frame_set: SynchronizedFrameSet,
    ) -> None:
        self.health.frame_set_received()
        try:
            self._queue.put_nowait(frame_set)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            self.health.frame_set_dropped()
            self._queue.put_nowait(frame_set)
        self.health.set_queue_depth(self._queue.qsize())

    def start(
        self,
        callback: Callable[[LiveAnalysisUpdate], None],
    ) -> None:
        if self._worker is not None:
            raise RuntimeError("live analysis runtime is already running")
        self._callback = callback
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._run_processing,
            name="video-pose-inference",
            daemon=True,
        )
        self._worker.start()
        self.gateway.start(self.enqueue_frame_set)

    def stop(self) -> RuleSessionUpdate:
        self.gateway.stop()
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            self._worker = None
        return self.rule_session.finish(self._last_timestamp_ms)

    def health_snapshot(self) -> LiveHealthSnapshot:
        return self.health.snapshot()

    def _run_processing(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                frame_set = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            started = time.perf_counter()
            try:
                update = self.process_frame_set(frame_set)
                latency_ms = (time.perf_counter() - started) * 1000.0
                self.health.frame_set_processed(latency_ms)
                if self._callback is not None:
                    self._callback(update)
            except Exception:
                self.health.processing_error()
            finally:
                self._queue.task_done()
                self.health.set_queue_depth(self._queue.qsize())


def build_live_runtime(
    config: LoadedAnalysisConfig,
    *,
    processing_queue_size: int = 2,
) -> LiveAnalysisRuntime:
    manifest = load_manifest(config.resolve(config.config.manifest))
    frame_store = MemoryFrameStore()
    health = LiveHealthRegistry(
        [
            camera.camera_id
            for camera in manifest.cameras
            if camera.enabled
        ],
        queue_capacity=processing_queue_size,
    )
    synchronizer = LiveFrameSynchronizer(manifest, frame_store)
    pipeline = build_analysis_pipeline(
        config,
        session_id=manifest.session_id,
        frame_loader=frame_store,
    )
    rule_session = RealtimeRuleSession(
        build_rule_engine(config),
        session_id=manifest.session_id,
    )
    gateway = ThreadedLiveGateway(
        manifest,
        synchronizer,
        health=health,
    )
    return LiveAnalysisRuntime(
        gateway=gateway,
        pipeline=pipeline,
        rule_session=rule_session,
        health=health,
        processing_queue_size=processing_queue_size,
    )
