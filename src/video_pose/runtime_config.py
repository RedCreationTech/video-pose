from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DetectorRuntimeConfig(BaseModel):
    weights: str
    confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    person_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    object_confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    device: str | None = None
    allowed_classes: set[str] | None = None
    class_aliases: dict[str, str] = Field(default_factory=dict)


class PoseRuntimeConfig(BaseModel):
    enabled: bool = True
    config: str
    checkpoint: str
    device: str = "cuda:0"


class RelationRuntimeConfig(BaseModel):
    hold_ratio: float = Field(default=0.2, gt=0.0)
    near_ratio: float = Field(default=0.75, gt=0.0)
    min_hold_px: float = Field(default=18.0, gt=0.0)
    min_near_px: float = Field(default=60.0, gt=0.0)
    hold_frames: int = Field(default=2, ge=1)
    free_frames: int = Field(default=2, ge=1)


class IdentityRuntimeConfig(BaseModel):
    enabled: bool = True
    distance_threshold: float = Field(default=120.0, gt=0.0)
    max_missed: int = Field(default=10, ge=0)


class TriangulationRuntimeConfig(BaseModel):
    enabled: bool = False
    calibration: str | None = None
    max_reprojection_rmse: float = Field(default=5.0, gt=0.0)


class IndustrialActionRuntimeConfig(BaseModel):
    tool_classes: set[str] = Field(default_factory=set)
    operation_zones: set[str] = Field(default_factory=set)
    tool_min_path_length: float = Field(default=40.0, gt=0.0)
    enable_zone_transitions: bool = False
    zone_entity_classes: set[str] = Field(default_factory=lambda: {"person"})
    inspect_zones: set[str] = Field(default_factory=set)
    inspect_entity_classes: set[str] = Field(
        default_factory=lambda: {"nose"}
    )
    inspect_dwell_frames: int = Field(default=5, ge=1)


class CaptureBackend(StrEnum):
    OPENCV = "opencv"
    GSTREAMER_OPENCV = "gstreamer-opencv"


class LiveCaptureRuntimeConfig(BaseModel):
    backend: CaptureBackend = CaptureBackend.OPENCV
    rtsp_transport: str = "tcp"
    latency_ms: int = Field(default=100, ge=0)
    appsink_max_buffers: int = Field(default=1, ge=1)
    appsink_drop: bool = True
    appsink_sync: bool = False
    decoder_element: str | None = None


class EvidenceRuntimeConfig(BaseModel):
    enabled: bool = False
    root: str = "../output/evidence"
    pre_roll_ms: int = Field(default=3000, ge=0)
    post_roll_ms: int = Field(default=3000, ge=0)
    sample_interval_ms: int = Field(default=200, ge=1)
    jpeg_quality: int = Field(default=70, ge=1, le=100)
    max_pending: int = Field(default=32, ge=1)
    worker_queue_size: int = Field(default=2, ge=1)


class OfflineAnalysisConfig(BaseModel):
    manifest: str
    rules: str
    calibration: str | None = None
    zones: str | None = None
    detector: DetectorRuntimeConfig
    pose: PoseRuntimeConfig | None = None
    relation: RelationRuntimeConfig = Field(default_factory=RelationRuntimeConfig)
    identity: IdentityRuntimeConfig = Field(default_factory=IdentityRuntimeConfig)
    triangulation: TriangulationRuntimeConfig = Field(
        default_factory=TriangulationRuntimeConfig
    )
    actions: IndustrialActionRuntimeConfig = Field(
        default_factory=IndustrialActionRuntimeConfig
    )
    live: LiveCaptureRuntimeConfig = Field(
        default_factory=LiveCaptureRuntimeConfig
    )
    evidence: EvidenceRuntimeConfig = Field(
        default_factory=EvidenceRuntimeConfig
    )
    action_min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class LoadedAnalysisConfig(BaseModel):
    path: Path
    config: OfflineAnalysisConfig

    def resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.path.parent / path).resolve()


def load_analysis_config(path: str | Path) -> LoadedAnalysisConfig:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = OfflineAnalysisConfig.model_validate(yaml.safe_load(handle))
    return LoadedAnalysisConfig(path=config_path, config=config)
