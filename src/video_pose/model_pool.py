from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from .adapters.mmpose_topdown import MMPoseTopDownEstimator
from .adapters.ultralytics_yolo import UltralyticsDetector
from .detections import TrackedDetection
from .live_health import ModelWarmupHealthSnapshot
from .observations import BoundingBox
from .runtime_config import LoadedAnalysisConfig
from .structured_log import log_event

LOGGER = logging.getLogger("video_pose.model")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PersistentModelPool:
    """Keep heavy detector/pose model backends loaded across sessions."""

    def __init__(
        self,
        *,
        detector: Any,
        pose_estimator: Any | None,
        warmup_enabled: bool = False,
        warmup_image_size: int = 640,
        warmup_max_latency_ms: float = 15000.0,
    ) -> None:
        self.detector = detector
        self.pose_estimator = pose_estimator
        self.warmup_enabled = warmup_enabled
        self.warmup_image_size = warmup_image_size
        self.warmup_max_latency_ms = warmup_max_latency_ms
        self._lock = threading.Lock()
        self._loaded = False
        self._warmup = ModelWarmupHealthSnapshot(
            enabled=warmup_enabled,
            status=(
                "NOT_RUN"
                if warmup_enabled
                else "DISABLED"
            ),
        )

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

    def warmup_health(self) -> ModelWarmupHealthSnapshot:
        with self._lock:
            return self._warmup.model_copy(deep=True)

    def warmup(
        self,
        *,
        force: bool = False,
    ) -> ModelWarmupHealthSnapshot:
        with self._lock:
            if not self.warmup_enabled:
                return self._warmup.model_copy(deep=True)
            if not self._loaded:
                raise RuntimeError(
                    "model pool must be loaded before warmup"
                )
            if self._warmup.status == "RUNNING":
                raise RuntimeError("model warmup is already running")
            if self._warmup.status == "PASS" and not force:
                return self._warmup.model_copy(deep=True)
            started_at = _utc_now()
            self._warmup = ModelWarmupHealthSnapshot(
                enabled=True,
                status="RUNNING",
                started_at=started_at,
            )

        started = time.perf_counter()
        detector_count = 0
        pose_count = 0
        error_type: str | None = None
        status = "PASS"

        try:
            import numpy as np

            image = np.zeros(
                (
                    self.warmup_image_size,
                    self.warmup_image_size,
                    3,
                ),
                dtype=np.uint8,
            )

            detect = getattr(self.detector, "detect", None)
            if not callable(detect):
                raise RuntimeError(
                    "detector does not expose detect()"
                )
            detections = detect(image)
            detector_count = len(detections)

            if self.pose_estimator is not None:
                infer = getattr(
                    self.pose_estimator,
                    "infer",
                    None,
                )
                if not callable(infer):
                    raise RuntimeError(
                        "pose estimator does not expose infer()"
                    )
                margin = self.warmup_image_size * 0.10
                person = TrackedDetection(
                    bbox=BoundingBox(
                        x1=margin,
                        y1=margin,
                        x2=self.warmup_image_size - margin,
                        y2=self.warmup_image_size - margin,
                    ),
                    confidence=1.0,
                    class_name="person",
                    entity_id="warmup-person",
                )
                poses = infer(image, [person])
                pose_count = len(poses)
        except Exception as exc:
            status = "FAIL"
            error_type = type(exc).__name__

        latency_ms = (
            time.perf_counter() - started
        ) * 1000.0
        completed_at = _utc_now()
        with self._lock:
            self._warmup = ModelWarmupHealthSnapshot(
                enabled=True,
                status=status,
                latency_ms=latency_ms,
                detector_result_count=detector_count,
                pose_result_count=pose_count,
                error_type=error_type,
                started_at=started_at,
                completed_at=completed_at,
            )
            snapshot = self._warmup.model_copy(deep=True)

        log_event(
            LOGGER,
            "model_warmup_completed",
            level=(
                logging.INFO
                if status == "PASS"
                else logging.ERROR
            ),
            status=status,
            latency_ms=round(latency_ms, 3),
            detector_result_count=detector_count,
            pose_result_count=pose_count,
            error_type=error_type,
        )
        return snapshot


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
        warmup_enabled=cfg.model_warmup.enabled,
        warmup_image_size=cfg.model_warmup.image_size,
        warmup_max_latency_ms=(
            cfg.model_warmup.max_latency_ms
        ),
    )
