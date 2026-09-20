from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from .observations import Point2D, Point3D


class PlanarCameraCalibration(BaseModel):
    camera_id: str
    homography: list[list[float]]

    @model_validator(mode="after")
    def validate_homography(self) -> PlanarCameraCalibration:
        if len(self.homography) != 3 or any(
            len(row) != 3 for row in self.homography
        ):
            raise ValueError("homography must be a 3x3 matrix")
        return self

    def image_to_world(self, point: Point2D) -> Point3D:
        matrix = self.homography
        denominator = (
            matrix[2][0] * point.x
            + matrix[2][1] * point.y
            + matrix[2][2]
        )
        if abs(denominator) < 1e-12:
            raise ValueError("homography maps point to infinity")
        world_x = (
            matrix[0][0] * point.x
            + matrix[0][1] * point.y
            + matrix[0][2]
        ) / denominator
        world_y = (
            matrix[1][0] * point.x
            + matrix[1][1] * point.y
            + matrix[1][2]
        ) / denominator
        return Point3D(x=world_x, y=world_y, z=0.0)


class PlanarCalibrationProfile(BaseModel):
    profile_id: str
    version: int = Field(ge=1)
    cameras: list[PlanarCameraCalibration]

    @model_validator(mode="after")
    def camera_ids_must_be_unique(self) -> PlanarCalibrationProfile:
        ids = [camera.camera_id for camera in self.cameras]
        if len(ids) != len(set(ids)):
            raise ValueError("camera calibration ids must be unique")
        return self

    def camera(self, camera_id: str) -> PlanarCameraCalibration | None:
        return next(
            (camera for camera in self.cameras if camera.camera_id == camera_id),
            None,
        )


def load_planar_calibration(path: str | Path) -> PlanarCalibrationProfile:
    with Path(path).open("r", encoding="utf-8") as handle:
        return PlanarCalibrationProfile.model_validate(yaml.safe_load(handle))
