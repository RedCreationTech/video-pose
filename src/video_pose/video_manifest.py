from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class CameraPosition(StrEnum):
    FRONT = "FRONT"
    REAR = "REAR"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class CameraReplaySource(BaseModel):
    camera_id: str
    position: CameraPosition
    uri: str
    clock_offset_ms: float = 0.0
    enabled: bool = True


class ReplayManifest(BaseModel):
    session_id: str
    workstation_id: str
    sync_tolerance_ms: float = Field(default=20.0, gt=0.0, le=500.0)
    cameras: list[CameraReplaySource]

    @model_validator(mode="after")
    def require_unique_cameras_and_four_positions(self) -> ReplayManifest:
        ids = [camera.camera_id for camera in self.cameras]
        if len(ids) != len(set(ids)):
            raise ValueError("camera_id must be unique")

        positions = [camera.position for camera in self.cameras if camera.enabled]
        if len(positions) != len(set(positions)):
            raise ValueError("enabled camera positions must be unique")

        required = set(CameraPosition)
        missing = required - set(positions)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"four-view replay requires camera positions: missing {names}")
        return self


def load_manifest(path: str | Path) -> ReplayManifest:
    with Path(path).open("r", encoding="utf-8") as handle:
        return ReplayManifest.model_validate(yaml.safe_load(handle))
