from __future__ import annotations

from math import sqrt
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from .observations import Point2D, Point3D


class PerspectiveCameraCalibration(BaseModel):
    camera_id: str
    projection: list[list[float]]

    @model_validator(mode="after")
    def validate_projection(self) -> PerspectiveCameraCalibration:
        if len(self.projection) != 3 or any(
            len(row) != 4 for row in self.projection
        ):
            raise ValueError("projection must be a 3x4 matrix")
        return self

    def project(self, point: Point3D) -> Point2D:
        vector = [point.x, point.y, point.z, 1.0]
        projected = [
            sum(row[index] * vector[index] for index in range(4))
            for row in self.projection
        ]
        if abs(projected[2]) < 1e-12:
            raise ValueError("point projects to infinity")
        return Point2D(
            x=projected[0] / projected[2],
            y=projected[1] / projected[2],
        )


class PerspectiveCalibrationProfile(BaseModel):
    profile_id: str
    version: int
    cameras: list[PerspectiveCameraCalibration]

    @model_validator(mode="after")
    def camera_ids_must_be_unique(self) -> PerspectiveCalibrationProfile:
        ids = [camera.camera_id for camera in self.cameras]
        if len(ids) != len(set(ids)):
            raise ValueError("camera ids must be unique")
        return self

    def camera(self, camera_id: str) -> PerspectiveCameraCalibration | None:
        return next(
            (camera for camera in self.cameras if camera.camera_id == camera_id),
            None,
        )


class TriangulationResult(BaseModel):
    point: Point3D
    reprojection_rmse: float
    camera_count: int


def load_perspective_calibration(
    path: str | Path,
) -> PerspectiveCalibrationProfile:
    with Path(path).open("r", encoding="utf-8") as handle:
        return PerspectiveCalibrationProfile.model_validate(
            yaml.safe_load(handle)
        )


def _solve_linear(
    matrix: list[list[float]],
    values: list[float],
) -> list[float]:
    size = len(values)
    augmented = [
        [float(value) for value in matrix[row]] + [float(values[row])]
        for row in range(size)
    ]
    for column in range(size):
        pivot = max(
            range(column, size),
            key=lambda row: abs(augmented[row][column]),
        )
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("triangulation system is singular")
        augmented[column], augmented[pivot] = (
            augmented[pivot],
            augmented[column],
        )
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[row][-1] for row in range(size)]


def triangulate_point(
    views: list[tuple[PerspectiveCameraCalibration, Point2D]],
) -> TriangulationResult:
    if len(views) < 2:
        raise ValueError("at least two camera views are required")

    rows: list[list[float]] = []
    values: list[float] = []
    for camera, point in views:
        projection = camera.projection
        u = point.x
        v = point.y
        rows.append(
            [
                projection[0][0] - u * projection[2][0],
                projection[0][1] - u * projection[2][1],
                projection[0][2] - u * projection[2][2],
            ]
        )
        values.append(u * projection[2][3] - projection[0][3])
        rows.append(
            [
                projection[1][0] - v * projection[2][0],
                projection[1][1] - v * projection[2][1],
                projection[1][2] - v * projection[2][2],
            ]
        )
        values.append(v * projection[2][3] - projection[1][3])

    normal = [[0.0 for _ in range(3)] for _ in range(3)]
    rhs = [0.0, 0.0, 0.0]
    for row, value in zip(rows, values, strict=True):
        for left in range(3):
            rhs[left] += row[left] * value
            for right in range(3):
                normal[left][right] += row[left] * row[right]
    solution = _solve_linear(normal, rhs)
    point = Point3D(x=solution[0], y=solution[1], z=solution[2])

    squared_errors: list[float] = []
    for camera, image_point in views:
        projected = camera.project(point)
        squared_errors.append(
            (projected.x - image_point.x) ** 2
            + (projected.y - image_point.y) ** 2
        )
    rmse = sqrt(sum(squared_errors) / len(squared_errors))
    return TriangulationResult(
        point=point,
        reprojection_rmse=rmse,
        camera_count=len(views),
    )
