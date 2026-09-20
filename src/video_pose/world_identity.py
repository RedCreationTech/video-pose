from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .observations import Observation, ObservationType, Point3D


def world_distance(left: Point3D, right: Point3D) -> float:
    return hypot(left.x - right.x, left.y - right.y)


@dataclass(slots=True)
class _WorldTrack:
    entity_id: str
    entity_class: str
    point: Point3D
    missed: int = 0


@dataclass(slots=True)
class _Cluster:
    entity_class: str
    observations: list[Observation]

    def centroid(self) -> Point3D:
        points = [
            observation.point_3d
            for observation in self.observations
            if observation.point_3d is not None
        ]
        if not points:
            raise ValueError("world cluster requires projected points")
        return Point3D(
            x=sum(point.x for point in points) / len(points),
            y=sum(point.y for point in points) / len(points),
            z=0.0,
        )


class MultiViewIdentityProcessor:
    """Associate same-class entities across cameras in planar world coordinates."""

    def __init__(
        self,
        *,
        distance_threshold: float = 120.0,
        max_missed: int = 10,
    ) -> None:
        self.distance_threshold = distance_threshold
        self.max_missed = max_missed
        self._tracks: list[_WorldTrack] = []
        self._next_id = 1

    def process(self, observations: list[Observation]) -> list[Observation]:
        entity_observations = [
            observation
            for observation in observations
            if observation.type in {ObservationType.PERSON, ObservationType.OBJECT}
            and observation.entity_class is not None
            and observation.point_3d is not None
        ]
        clusters = self._cluster(entity_observations)
        local_to_world: dict[str, str] = {}

        for track in self._tracks:
            track.missed += 1

        used_tracks: set[int] = set()
        for cluster in clusters:
            centroid = cluster.centroid()
            track_index = self._match_track(
                cluster.entity_class,
                centroid,
                used_tracks,
            )
            if track_index is None:
                world_id = (
                    f"world-{cluster.entity_class}-{self._next_id:04d}"
                )
                self._next_id += 1
                self._tracks.append(
                    _WorldTrack(
                        entity_id=world_id,
                        entity_class=cluster.entity_class,
                        point=centroid,
                        missed=0,
                    )
                )
                used_tracks.add(len(self._tracks) - 1)
            else:
                track = self._tracks[track_index]
                track.point = centroid
                track.missed = 0
                world_id = track.entity_id
                used_tracks.add(track_index)

            for observation in cluster.observations:
                local_to_world[observation.entity_id] = world_id

        self._tracks = [
            track for track in self._tracks if track.missed <= self.max_missed
        ]
        return [
            self._rewrite_observation(observation, local_to_world)
            for observation in observations
        ]

    def _cluster(self, observations: list[Observation]) -> list[_Cluster]:
        clusters: list[_Cluster] = []
        for observation in sorted(
            observations,
            key=lambda item: (
                item.entity_class or "",
                item.camera_id,
                item.entity_id,
            ),
        ):
            assert observation.entity_class is not None
            assert observation.point_3d is not None
            best: _Cluster | None = None
            best_distance = self.distance_threshold
            for cluster in clusters:
                if cluster.entity_class != observation.entity_class:
                    continue
                distance = world_distance(
                    cluster.centroid(),
                    observation.point_3d,
                )
                if distance <= best_distance:
                    best = cluster
                    best_distance = distance
            if best is None:
                clusters.append(
                    _Cluster(
                        entity_class=observation.entity_class,
                        observations=[observation],
                    )
                )
            else:
                best.observations.append(observation)
        return clusters

    def _match_track(
        self,
        entity_class: str,
        point: Point3D,
        used_tracks: set[int],
    ) -> int | None:
        best_index: int | None = None
        best_distance = self.distance_threshold
        for index, track in enumerate(self._tracks):
            if index in used_tracks or track.entity_class != entity_class:
                continue
            distance = world_distance(track.point, point)
            if distance <= best_distance:
                best_index = index
                best_distance = distance
        return best_index

    def _rewrite_observation(
        self,
        observation: Observation,
        local_to_world: dict[str, str],
    ) -> Observation:
        world_id = local_to_world.get(observation.entity_id)
        if world_id is not None:
            return self._copy_with_world_id(observation, world_id)

        if observation.type != ObservationType.BODY_KEYPOINT:
            return observation
        local_person = observation.attributes.get("person_id")
        if not isinstance(local_person, str):
            return observation
        world_person = local_to_world.get(local_person)
        if world_person is None:
            return observation

        keypoint_name = observation.entity_class or "keypoint"
        attributes = {
            **observation.attributes,
            "source_person_id": local_person,
            "person_id": world_person,
        }
        return observation.model_copy(
            update={
                "entity_id": f"{world_person}:{keypoint_name}",
                "attributes": attributes,
            }
        )

    @staticmethod
    def _copy_with_world_id(
        observation: Observation,
        world_id: str,
    ) -> Observation:
        attributes = {
            **observation.attributes,
            "source_entity_id": observation.entity_id,
        }
        return observation.model_copy(
            update={
                "entity_id": world_id,
                "attributes": attributes,
            }
        )
