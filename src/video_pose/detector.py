from __future__ import annotations

from typing import Protocol, Any

from .detections import Detection


class ObjectDetector(Protocol):
    model_name: str
    model_version: str

    def detect(self, image: Any) -> list[Detection]: ...
