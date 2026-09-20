from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .live_gateway import ThreadedLiveGateway
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
    """Connect live synchronized frames to AI pipeline and realtime rules."""

    def __init__(
        self,
        *,
        gateway: ThreadedLiveGateway,
        pipeline: VideoPosePipeline,
        rule_session: RealtimeRuleSession,
    ) -> None:
        self.gateway = gateway
        self.pipeline = pipeline
        self.rule_session = rule_session
        self._last_timestamp_ms = 0
        self._callback: Callable[[LiveAnalysisUpdate], None] | None = None

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

    def start(
        self,
        callback: Callable[[LiveAnalysisUpdate], None],
    ) -> None:
        self._callback = callback
        self.gateway.start(self._handle_frame_set)

    def stop(self) -> RuleSessionUpdate:
        self.gateway.stop()
        return self.rule_session.finish(self._last_timestamp_ms)

    def _handle_frame_set(
        self,
        frame_set: SynchronizedFrameSet,
    ) -> None:
        update = self.process_frame_set(frame_set)
        if self._callback is not None:
            self._callback(update)


def build_live_runtime(
    config: LoadedAnalysisConfig,
) -> LiveAnalysisRuntime:
    manifest = load_manifest(config.resolve(config.config.manifest))
    frame_store = MemoryFrameStore()
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
    gateway = ThreadedLiveGateway(manifest, synchronizer)
    return LiveAnalysisRuntime(
        gateway=gateway,
        pipeline=pipeline,
        rule_session=rule_session,
    )
