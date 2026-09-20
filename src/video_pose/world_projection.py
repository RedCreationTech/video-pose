from __future__ import annotations

from .calibration import PlanarCalibrationProfile
from .observations import Observation, ObservationType, Point2D


class WorldProjectionProcessor:
    """Project image-space object/person/keypoint locations onto the work plane."""

    def __init__(
        self,
        profile: PlanarCalibrationProfile,
        *,
        box_anchor: str = "center",
    ) -> None:
        if box_anchor not in {"center", "bottom_center"}:
            raise ValueError("box_anchor must be center or bottom_center")
        self.profile = profile
        self.box_anchor = box_anchor

    def process(self, observations: list[Observation]) -> list[Observation]:
        output: list[Observation] = []
        for observation in observations:
            calibration = self.profile.camera(observation.camera_id)
            if calibration is None:
                output.append(observation)
                continue

            image_point = self._image_point(observation)
            if image_point is None:
                output.append(observation)
                continue

            world_point = calibration.image_to_world(image_point)
            attributes = {
                **observation.attributes,
                "calibration_profile_id": self.profile.profile_id,
                "calibration_version": self.profile.version,
            }
            output.append(
                observation.model_copy(
                    update={
                        "point_3d": world_point,
                        "attributes": attributes,
                    }
                )
            )
        return output

    def _image_point(self, observation: Observation) -> Point2D | None:
        if observation.type == ObservationType.BODY_KEYPOINT:
            return observation.point_2d
        if observation.type not in {
            ObservationType.OBJECT,
            ObservationType.PERSON,
        }:
            return None
        if observation.bbox is None:
            return None

        center_x = (observation.bbox.x1 + observation.bbox.x2) / 2.0
        if self.box_anchor == "bottom_center":
            return Point2D(x=center_x, y=observation.bbox.y2)
        return Point2D(
            x=center_x,
            y=(observation.bbox.y1 + observation.bbox.y2) / 2.0,
        )
