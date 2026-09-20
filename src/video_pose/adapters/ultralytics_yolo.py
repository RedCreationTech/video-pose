from __future__ import annotations

from typing import Any

from ..detections import Detection
from ..observations import BoundingBox


def _to_list(value: Any) -> list[Any]:
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


class UltralyticsDetector:
    """Thin adapter around the public Ultralytics Results.boxes API."""

    model_name = "ultralytics-yolo"

    def __init__(
        self,
        weights: str,
        *,
        confidence: float = 0.25,
        device: str | None = None,
        allowed_classes: set[str] | None = None,
        class_aliases: dict[str, str] | None = None,
        model: Any | None = None,
        model_version: str | None = None,
    ) -> None:
        self.weights = weights
        self.confidence = confidence
        self.device = device
        self.allowed_classes = allowed_classes
        self.class_aliases = class_aliases or {}
        self.model_version = model_version or weights
        self._model = model

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "UltralyticsDetector requires the optional 'yolo' dependencies"
            ) from exc
        self._model = YOLO(self.weights)
        return self._model

    def detect(self, image: Any) -> list[Detection]:
        model = self._load_model()
        kwargs: dict[str, Any] = {
            "source": image,
            "conf": self.confidence,
            "verbose": False,
        }
        if self.device is not None:
            kwargs["device"] = self.device
        results = model.predict(**kwargs)
        if not results:
            return []

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        xyxy = _to_list(boxes.xyxy)
        confidences = _to_list(boxes.conf)
        classes = _to_list(boxes.cls)
        names = result.names

        output: list[Detection] = []
        for index, coordinates in enumerate(xyxy):
            class_id = int(classes[index])
            raw_name = str(names[class_id])
            class_name = self.class_aliases.get(raw_name, raw_name)
            if (
                self.allowed_classes is not None
                and class_name not in self.allowed_classes
            ):
                continue
            output.append(
                Detection(
                    bbox=BoundingBox(
                        x1=float(coordinates[0]),
                        y1=float(coordinates[1]),
                        x2=float(coordinates[2]),
                        y2=float(coordinates[3]),
                    ),
                    confidence=float(confidences[index]),
                    class_name=class_name,
                    class_id=class_id,
                    source_id=str(index),
                )
            )
        return output
