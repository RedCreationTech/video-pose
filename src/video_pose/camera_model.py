from __future__ import annotations

from math import sqrt
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from .observations import Point2D, Point3D
from .perspective import (
    PerspectiveCalibrationProfile,
    PerspectiveCameraCalibration,
)


class CameraIntrinsics(BaseModel):
    fx: float
    fy: float
    cx: float
    cy: float
    skew: float = 0.0

    def matrix(self) -> list[list[float]]:
        return [
            [self.fx, self.skew, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ]


class CameraExtrinsics(BaseModel):
    rotation: list[list[float]]
    translation: list[float]

    @model_validator(mode="after")
    def validate_shape(self) -> CameraExtrinsics:
        if len(self.rotation) != 3 or any(
            len(row) != 3 for row in self.rotation
        ):
            raise ValueError("rotation must be 3x3")
        if len(self.translation) != 3:
            raise ValueError("translation must contain 3 values")
        return self

    def matrix(self) -> list[list[float]]:
        return [
            [*self.rotation[row], self.translation[row]]
            for row in range(3)
        ]


class CameraModelDefinition(BaseModel):
    camera_id: str
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics


class CameraModelProfile(BaseModel):
    profile_id: str
    version: int = Field(ge=1)
    cameras: list[CameraModelDefinition]


class CalibrationControlPoint(BaseModel):
    camera_id: str
    world: Point3D
    image: Point2D


class CalibrationControlSet(BaseModel):
    points: list[CalibrationControlPoint]


class CameraHealth(BaseModel):
    camera_id: str
    point_count: int
    rmse: float
    max_error: float
    passed: bool


class CalibrationHealthReport(BaseModel):
    profile_id: str
    version: int
    max_allowed_rmse: float
    cameras: list[CameraHealth]

    @property
    def passed(self) -> bool:
        return bool(self.cameras) and all(camera.passed for camera in self.cameras)


def _multiply(
    left: list[list[float]],
    right: list[list[float]],
) -> list[list[float]]:
    rows = len(left)
    shared = len(right)
    columns = len(right[0])
    if len(left[0]) != shared:
        raise ValueError("matrix shape mismatch")
    return [
        [
            sum(left[row][k] * right[k][column] for k in range(shared))
            for column in range(columns)
        ]
        for row in range(rows)
    ]


def build_projection_camera(
    definition: CameraModelDefinition,
) -> PerspectiveCameraCalibration:
    projection = _multiply(
        definition.intrinsics.matrix(),
        definition.extrinsics.matrix(),
    )
    return PerspectiveCameraCalibration(
        camera_id=definition.camera_id,
        projection=projection,
    )


def build_perspective_profile(
    profile: CameraModelProfile,
) -> PerspectiveCalibrationProfile:
    return PerspectiveCalibrationProfile(
        profile_id=profile.profile_id,
        version=profile.version,
        cameras=[
            build_projection_camera(camera)
            for camera in profile.cameras
        ],
    )


def load_camera_model_profile(path: str | Path) -> CameraModelProfile:
    with Path(path).open("r", encoding="utf-8") as handle:
        return CameraModelProfile.model_validate(yaml.safe_load(handle))


def load_control_points(path: str | Path) -> CalibrationControlSet:
    with Path(path).open("r", encoding="utf-8") as handle:
        return CalibrationControlSet.model_validate(yaml.safe_load(handle))


def validate_calibration_health(
    profile: PerspectiveCalibrationProfile,
    control_points: CalibrationControlSet,
    *,
    max_rmse: float,
) -> CalibrationHealthReport:
    grouped: dict[str, list[CalibrationControlPoint]] = {}
    for point in control_points.points:
        grouped.setdefault(point.camera_id, []).append(point)

    cameras: list[CameraHealth] = []
    for camera in profile.cameras:
        points = grouped.get(camera.camera_id, [])
        errors: list[float] = []
        for point in points:
            projected = camera.project(point.world)
            errors.append(
                sqrt(
                    (projected.x - point.image.x) ** 2
                    + (projected.y - point.image.y) ** 2
                )
            )
        if errors:
            rmse = sqrt(
                sum(error * error for error in errors) / len(errors)
            )
            maximum = max(errors)
        else:
            rmse = float("inf")
            maximum = float("inf")
        cameras.append(
            CameraHealth(
                camera_id=camera.camera_id,
                point_count=len(points),
                rmse=rmse,
                max_error=maximum,
                passed=bool(points) and rmse <= max_rmse,
            )
        )

    return CalibrationHealthReport(
        profile_id=profile.profile_id,
        version=profile.version,
        max_allowed_rmse=max_rmse,
        cameras=cameras,
    )
