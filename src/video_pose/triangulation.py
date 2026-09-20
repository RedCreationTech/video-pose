from __future__ import annotations

from collections import defaultdict

from .observations import Observation, ObservationType, Point2D
from .perspective import (
    PerspectiveCalibrationProfile,
    PerspectiveCameraCalibration,
    triangulate_point,
)


class TriangulationProcessor:
    """Triangulate canonical world entities after multi-view identity fusion."""

    def __init__(
        self,
        profile: PerspectiveCalibrationProfile,
        *,
        max_reprojection_rmse: float = 5.0,
    ) -> None:
        self.profile = profile
        self.max_reprojection_rmse = max_reprojection_rmse

    def process(self, observations: list[Observation]) -> list[Observation]:
        groups: dict[str, list[Observation]] = defaultdict(list)
        for observation in observations:
            if self._image_point(observation) is None:
                continue
            if self.profile.camera(observation.camera_id) is None:
                continue
            groups[observation.entity_id].append(observation)

        updates: dict[str, tuple[object, float, int]] = {}
        for entity_id, group in groups.items():
            unique_cameras = {item.camera_id for item in group}
            if len(unique_cameras) < 2:
                continue
            views: list[
                tuple[PerspectiveCameraCalibration, Point2D]
            ] = []
            for observation in group:
                camera = self.profile.camera(observation.camera_id)
                point = self._image_point(observation)
                if camera is not None and point is not None:
                    views.append((camera, point))
            result = triangulate_point(views)
            if result.reprojection_rmse <= self.max_reprojection_rmse:
                updates[entity_id] = (
                    result.point,
                    result.reprojection_rmse,
                    result.camera_count,
                )

        output: list[Observation] = []
        for observation in observations:
            update = updates.get(observation.entity_id)
            if update is None:
                output.append(observation)
                continue
            point, rmse, camera_count = update
            attributes = {
                **observation.attributes,
                "triangulation_profile_id": self.profile.profile_id,
                "triangulation_profile_version": self.profile.version,
                "reprojection_rmse": rmse,
                "triangulated_views": camera_count,
            }
            output.append(
                observation.model_copy(
                    update={
                        "point_3d": point,
                        "attributes": attributes,
                    }
                )
            )
        return output

    @staticmethod
    def _image_point(observation: Observation) -> Point2D | None:
        if observation.type == ObservationType.BODY_KEYPOINT:
            return observation.point_2d
        if observation.type not in {
            ObservationType.PERSON,
            ObservationType.OBJECT,
        }:
            return None
        if observation.bbox is None:
            return None
        return Point2D(
            x=(observation.bbox.x1 + observation.bbox.x2) / 2.0,
            y=(observation.bbox.y1 + observation.bbox.y2) / 2.0,
        )
