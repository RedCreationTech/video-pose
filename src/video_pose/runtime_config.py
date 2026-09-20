from __future__ import annotations

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


class OfflineAnalysisConfig(BaseModel):
    manifest: str
    rules: str
    calibration: str | None = None
    zones: str | None = None
    detector: DetectorRuntimeConfig
    pose: PoseRuntimeConfig | None = None
    relation: RelationRuntimeConfig = Field(default_factory=RelationRuntimeConfig)
    identity: IdentityRuntimeConfig = Field(default_factory=IdentityRuntimeConfig)
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
