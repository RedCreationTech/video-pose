from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from .live_runtime import LiveAnalysisUpdate
from .model_pool import PersistentModelPool
from .persistent_camera import PersistentCameraHub
from .pipeline import VideoPosePipeline
from .realtime_rules import RealtimeRuleSession, RuleSessionUpdate
from .resource_usage import sample_process_resources
from .runtime_builder import build_analysis_pipeline, build_rule_engine
from .runtime_config import LoadedAnalysisConfig
from .video_replay import SynchronizedFrameSet


class SessionAnalysisRuntime:
    """Session-scoped inference/rules over persistent cameras and models."""

    def __init__(
        self,
        *,
        hub: PersistentCameraHub,
        pipeline: VideoPosePipeline,
        rule_session: RealtimeRuleSession,
        processing_queue_size: int = 2,
        resource_sample_every: int = 30,
    ) -> None:
        if processing_queue_size < 1:
            raise ValueError("processing_queue_size must be >= 1")
        if resource_sample_every < 1:
            raise ValueError("resource_sample_every must be >= 1")
        self.hub = hub
        self.pipeline = pipeline
        self.rule_session = rule_session
        self.health = hub.health
        self.resource_sample_every = resource_sample_every
        self._processed_since_resource_sample = 0
        self._last_timestamp_ms = 0
        self._callback: Callable[[LiveAnalysisUpdate], None] | None = None
        self._queue: queue.Queue[SynchronizedFrameSet] = queue.Queue(
            maxsize=processing_queue_size
        )
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._subscription_token: str | None = None

    def process_frame_set(
        self,
        frame_set: SynchronizedFrameSet,
    ) -> LiveAnalysisUpdate:
        trace = self.pipeline.process_with_trace([frame_set])[0]
        now_ms = round(frame_set.reference_timestamp_ms)
        self._last_timestamp_ms = max(self._last_timestamp_ms, now_ms)

        updates: list[RuleSessionUpdate] = []
        if trace.actions:
            for action in trace.actions:
                updates.append(self.rule_session.ingest(action))
        else:
            updates.append(self.rule_session.tick(now_ms))

        return LiveAnalysisUpdate(
            trace=trace,
            rule_updates=tuple(updates),
        )

    def enqueue_frame_set(
        self,
        frame_set: SynchronizedFrameSet,
    ) -> None:
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
            raise RuntimeError("session analysis runtime is already running")
        if not self.hub.running:
            raise RuntimeError("persistent camera hub is not running")

        self._callback = callback
        self._stop.clear()
        self.health.record_resources(sample_process_resources())
        self._worker = threading.Thread(
            target=self._run_processing,
            name="video-pose-session-inference",
            daemon=True,
        )
        self._worker.start()
        self._subscription_token = self.hub.subscribe(
            self.enqueue_frame_set
        )

    def stop(self) -> RuleSessionUpdate:
        if self._subscription_token is not None:
            self.hub.unsubscribe(self._subscription_token)
            self._subscription_token = None
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            self._worker = None
        self.health.set_queue_depth(0)
        self.health.record_resources(sample_process_resources())
        return self.rule_session.finish(self._last_timestamp_ms)

    def health_snapshot(self):
        return self.hub.health_snapshot()

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
                self._processed_since_resource_sample += 1
                if (
                    self._processed_since_resource_sample
                    >= self.resource_sample_every
                ):
                    self.health.record_resources(
                        sample_process_resources()
                    )
                    self._processed_since_resource_sample = 0
                if self._callback is not None:
                    self._callback(update)
            except Exception:
                self.health.processing_error()
            finally:
                self._queue.task_done()
                self.health.set_queue_depth(self._queue.qsize())


def build_session_analysis_runtime(
    config: LoadedAnalysisConfig,
    *,
    hub: PersistentCameraHub,
    session_id: str,
    processing_queue_size: int = 2,
    model_pool: PersistentModelPool | None = None,
) -> SessionAnalysisRuntime:
    pipeline = build_analysis_pipeline(
        config,
        session_id=session_id,
        frame_loader=hub.frame_store,
        model_pool=model_pool,
    )
    rule_session = RealtimeRuleSession(
        build_rule_engine(config),
        session_id=session_id,
    )
    return SessionAnalysisRuntime(
        hub=hub,
        pipeline=pipeline,
        rule_session=rule_session,
        processing_queue_size=processing_queue_size,
    )
