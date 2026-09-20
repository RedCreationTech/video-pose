from __future__ import annotations

from dataclasses import dataclass

from .adapters.opencv_file import OpenCVFileFrameLoader
from .pipeline import VideoPosePipeline
from .rules import RuleEngine
from .runtime_builder import build_analysis_pipeline, build_rule_engine
from .runtime_config import LoadedAnalysisConfig
from .video_replay import ReplayPlanner


@dataclass(slots=True)
class OfflineAnalysisRuntime:
    config: LoadedAnalysisConfig
    frame_loader: OpenCVFileFrameLoader
    planner: ReplayPlanner
    pipeline: VideoPosePipeline
    rule_engine: RuleEngine

    def close(self) -> None:
        self.frame_loader.close()

    def __enter__(self) -> OfflineAnalysisRuntime:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def build_offline_runtime(config: LoadedAnalysisConfig) -> OfflineAnalysisRuntime:
    manifest_path = config.resolve(config.config.manifest)
    planner = ReplayPlanner.from_manifest_file(manifest_path)
    frame_loader = OpenCVFileFrameLoader()
    pipeline = build_analysis_pipeline(
        config,
        session_id=planner.manifest.session_id,
        frame_loader=frame_loader,
    )
    return OfflineAnalysisRuntime(
        config=config,
        frame_loader=frame_loader,
        planner=planner,
        pipeline=pipeline,
        rule_engine=build_rule_engine(config),
    )
