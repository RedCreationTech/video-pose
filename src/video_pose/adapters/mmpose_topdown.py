from __future__ import annotations

from typing import Any, Callable

from ..detections import TrackedDetection
from ..pose import COCO_KEYPOINT_NAMES, PoseEstimate, PoseKeypoint


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def _unwrap_single_instance(value: list[Any]) -> list[Any]:
    if len(value) == 1 and isinstance(value[0], list):
        return value[0]
    return value


class MMPoseTopDownEstimator:
    """MMPose 1.x top-down pose adapter using inference_topdown."""

    def __init__(
        self,
        config: str,
        checkpoint: str,
        *,
        device: str = "cuda:0",
        keypoint_names: tuple[str, ...] = COCO_KEYPOINT_NAMES,
        model: Any | None = None,
        inference_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self.checkpoint = checkpoint
        self.device = device
        self.keypoint_names = keypoint_names
        self._model = model
        self._inference_fn = inference_fn

    def _load(self) -> tuple[Any, Callable[..., Any]]:
        if self._model is not None and self._inference_fn is not None:
            return self._model, self._inference_fn
        try:
            from mmpose.apis import inference_topdown, init_model
            from mmpose.utils import register_all_modules
        except ImportError as exc:
            raise RuntimeError(
                "MMPoseTopDownEstimator requires a compatible MMPose/MMCV stack"
            ) from exc

        register_all_modules()
        self._model = init_model(
            self.config,
            self.checkpoint,
            device=self.device,
        )
        self._inference_fn = inference_topdown
        return self._model, self._inference_fn

    def infer(
        self,
        image: Any,
        persons: list[TrackedDetection],
    ) -> list[PoseEstimate]:
        if not persons:
            return []
        model, inference_fn = self._load()
        bboxes = [
            [
                person.bbox.x1,
                person.bbox.y1,
                person.bbox.x2,
                person.bbox.y2,
            ]
            for person in persons
        ]
        samples = inference_fn(
            model,
            image,
            bboxes=bboxes,
            bbox_format="xyxy",
        )

        output: list[PoseEstimate] = []
        for person, sample in zip(persons, samples, strict=False):
            instances = sample.pred_instances
            raw_keypoints = _unwrap_single_instance(_to_list(instances.keypoints))
            raw_scores = _unwrap_single_instance(
                _to_list(instances.keypoint_scores)
            )
            keypoints: list[PoseKeypoint] = []
            for index, coordinates in enumerate(raw_keypoints):
                if index >= len(self.keypoint_names):
                    break
                score = float(raw_scores[index]) if index < len(raw_scores) else 0.0
                keypoints.append(
                    PoseKeypoint(
                        name=self.keypoint_names[index],
                        x=float(coordinates[0]),
                        y=float(coordinates[1]),
                        confidence=score,
                    )
                )
            output.append(
                PoseEstimate(
                    person_entity_id=person.entity_id,
                    keypoints=tuple(keypoints),
                )
            )
        return output
