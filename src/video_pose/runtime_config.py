from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

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
    GSTREAMER_NATIVE = "gstreamer-native"


class CaptureTimestampSource(StrEnum):
    ARRIVAL = "arrival"
    PTS = "pts"
    REFERENCE = "reference"


class LiveCaptureRuntimeConfig(BaseModel):
    backend: CaptureBackend = CaptureBackend.OPENCV
    rtsp_transport: str = "tcp"
    latency_ms: int = Field(default=100, ge=0)
    appsink_max_buffers: int = Field(default=1, ge=1)
    appsink_drop: bool = True
    appsink_sync: bool = False
    decoder_element: str | None = None
    native_timestamp_source: CaptureTimestampSource = (
        CaptureTimestampSource.PTS
    )
    native_pull_timeout_ms: int = Field(default=1000, ge=1)
    native_ntp_sync: bool = False
    native_rfc7273_sync: bool = False


def effective_capture_timestamp_source(
    config: LiveCaptureRuntimeConfig,
) -> CaptureTimestampSource:
    if config.backend == CaptureBackend.GSTREAMER_NATIVE:
        return config.native_timestamp_source
    return CaptureTimestampSource.ARRIVAL


class SessionQualityRuntimeConfig(BaseModel):
    enabled: bool = False
    monitor_cameras: bool = True
    monitor_sync: bool = True
    poll_interval_ms: int = Field(default=500, ge=100)
    camera_grace_ms: int = Field(default=3000, ge=0)
    max_camera_staleness_ms: int = Field(default=3000, ge=1)
    sync_grace_ms: int = Field(default=3000, ge=0)
    max_sync_miss_ratio: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
    )
    max_sync_p99_skew_ms: float = Field(default=30.0, ge=0.0)
    max_abs_sync_drift_ms_per_minute: float = Field(
        default=3.0,
        ge=0.0,
    )
    monitor_processing: bool = False
    processing_grace_ms: int = Field(default=3000, ge=0)
    max_processing_error_delta: int = Field(default=0, ge=0)
    max_processing_drop_ratio: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
    )
    monitor_evidence: bool = False
    evidence_grace_ms: int = Field(default=3000, ge=0)
    max_evidence_error_delta: int = Field(default=0, ge=0)
    max_evidence_drop_ratio: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
    )
    block_evidence_over_capacity: bool = True
    severity: Literal["MINOR", "MAJOR", "CRITICAL"] = "CRITICAL"


class CalibrationHealthRuntimeConfig(BaseModel):
    enabled: bool = False
    calibration: str | None = None
    control_points: str | None = None
    max_rmse: float = Field(default=5.0, gt=0.0)


class SessionReadinessRuntimeConfig(BaseModel):
    enabled: bool = False
    require_all_cameras_online: bool = True
    allow_camera_degraded: bool = False
    require_sync: bool = True
    min_sync_emitted_total: int = Field(default=30, ge=0)
    max_sync_miss_ratio: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
    )
    max_sync_p99_skew_ms: float = Field(default=20.0, ge=0.0)
    max_abs_sync_drift_ms_per_minute: float = Field(
        default=2.0,
        ge=0.0,
    )
    block_evidence_over_capacity: bool = True
    block_evidence_errors: bool = True
    require_persistence: bool = False
    block_persistence_degraded: bool = False
    require_runtime_assets: bool = True
    require_storage_headroom: bool = True
    min_storage_free_ratio: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
    )
    min_storage_free_gb: float = Field(default=5.0, ge=0.0)


class EvidenceRuntimeConfig(BaseModel):
    enabled: bool = False
    root: str = "../output/evidence"
    pre_roll_ms: int = Field(default=3000, ge=0)
    post_roll_ms: int = Field(default=3000, ge=0)
    sample_interval_ms: int = Field(default=200, ge=1)
    jpeg_quality: int = Field(default=70, ge=1, le=100)
    max_pending: int = Field(default=32, ge=1)
    worker_queue_size: int = Field(default=2, ge=1)
    retention_days: int = Field(default=180, ge=1)
    max_total_gb: float = Field(default=50.0, gt=0.0)
    protect_unreviewed: bool = True
    cleanup_interval_s: int = Field(default=3600, ge=60)


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
    readiness: SessionReadinessRuntimeConfig = Field(
        default_factory=SessionReadinessRuntimeConfig
    )
    calibration_health: CalibrationHealthRuntimeConfig = Field(
        default_factory=CalibrationHealthRuntimeConfig
    )
    session_quality: SessionQualityRuntimeConfig = Field(
        default_factory=SessionQualityRuntimeConfig
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
