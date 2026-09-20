from __future__ import annotations

from math import sqrt

from pydantic import BaseModel, Field

from .calibration import PlanarCameraCalibration
from .observations import Point2D


class HomographyCorrespondence(BaseModel):
    image: Point2D
    world: Point2D


class HomographyFitResult(BaseModel):
    homography: list[list[float]]
    rmse: float = Field(ge=0.0)
    point_errors: list[float]


def _solve_linear(matrix: list[list[float]], values: list[float]) -> list[float]:
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
            raise ValueError("homography system is singular")
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


def _least_squares(
    rows: list[list[float]],
    values: list[float],
) -> list[float]:
    columns = len(rows[0])
    normal = [[0.0 for _ in range(columns)] for _ in range(columns)]
    rhs = [0.0 for _ in range(columns)]
    for row, value in zip(rows, values, strict=True):
        for left in range(columns):
            rhs[left] += row[left] * value
            for right in range(columns):
                normal[left][right] += row[left] * row[right]
    return _solve_linear(normal, rhs)


def fit_homography(
    correspondences: list[HomographyCorrespondence],
) -> HomographyFitResult:
    if len(correspondences) < 4:
        raise ValueError("at least four correspondences are required")

    rows: list[list[float]] = []
    values: list[float] = []
    for item in correspondences:
        x = item.image.x
        y = item.image.y
        world_x = item.world.x
        world_y = item.world.y
        rows.append(
            [x, y, 1.0, 0.0, 0.0, 0.0, -world_x * x, -world_x * y]
        )
        values.append(world_x)
        rows.append(
            [0.0, 0.0, 0.0, x, y, 1.0, -world_y * x, -world_y * y]
        )
        values.append(world_y)

    solution = _least_squares(rows, values)
    homography = [
        solution[0:3],
        solution[3:6],
        [solution[6], solution[7], 1.0],
    ]
    calibration = PlanarCameraCalibration(
        camera_id="fit",
        homography=homography,
    )

    errors: list[float] = []
    for item in correspondences:
        projected = calibration.image_to_world(item.image)
        errors.append(
            sqrt(
                (projected.x - item.world.x) ** 2
                + (projected.y - item.world.y) ** 2
            )
        )
    rmse = sqrt(sum(error * error for error in errors) / len(errors))
    return HomographyFitResult(
        homography=homography,
        rmse=rmse,
        point_errors=errors,
    )
