from __future__ import annotations

import threading
from typing import Any

from .adapters.mmpose_topdown import MMPoseTopDownEstimator
from .adapters.ultralytics_yolo import UltralyticsDetector
from .runtime_config import LoadedAnalysisConfig


class PersistentModelPool:
    """Keep heavy detector/pose model backends loaded across sessions."""

    def __init__(
        self,
        *,
        detector: Any,
        pose_estimator: Any | None,
    ) -> None:
        self.detector = detector
        self.pose_estimator = pose_estimator
        self._lock = threading.Lock()
        self._loaded = False

    @property
    def loaded(self) -> bool:
        with self._lock:
            return self._loaded

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            detector_loader = getattr(self.detector, "load", None)
            if callable(detector_loader):
                detector_loader()
            if self.pose_estimator is not None:
                pose_loader = getattr(self.pose_estimator, "load", None)
                if callable(pose_loader):
                    pose_loader()
            self._loaded = True


def build_persistent_model_pool(
    config: LoadedAnalysisConfig,
) -> PersistentModelPool:
    cfg = config.config
    detector = UltralyticsDetector(
        str(config.resolve(cfg.detector.weights)),
        confidence=cfg.detector.confidence,
        device=cfg.detector.device,
        allowed_classes=cfg.detector.allowed_classes,
        class_aliases=cfg.detector.class_aliases,
    )

    pose_estimator = None
    if cfg.pose is not None and cfg.pose.enabled:
        pose_estimator = MMPoseTopDownEstimator(
            str(config.resolve(cfg.pose.config)),
            str(config.resolve(cfg.pose.checkpoint)),
            device=cfg.pose.device,
        )

    return PersistentModelPool(
        detector=detector,
        pose_estimator=pose_estimator,
    )
