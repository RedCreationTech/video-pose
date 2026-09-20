from __future__ import annotations

from .action_composite import CompositeActionRecognizer
from .adapters.mmpose_topdown import MMPoseTopDownEstimator
from .adapters.ultralytics_yolo import UltralyticsDetector
from .baseline_action import PickPlaceActionRecognizer
from .calibration import load_planar_calibration
from .contracts import ActionType
from .dwell_action import DwellZoneActionRecognizer
from .model_pool import PersistentModelPool
from .perception import FrameLoader, MultiViewPerceptionAdapter
from .perception_v1 import PerceptionV1Model
from .perspective import load_perspective_calibration
from .pipeline import VideoPosePipeline
from .relations import HumanObjectRelationBuilder
from .rules import RuleEngine
from .runtime_config import LoadedAnalysisConfig
from .tool_operation import ToolOperationRecognizer
from .triangulation import TriangulationProcessor
from .world_identity import MultiViewIdentityProcessor
from .world_projection import WorldProjectionProcessor
from .zone_actions import ZoneTransitionRecognizer
from .zones import ZoneRelationBuilder, load_zones


def _build_models(
    config: LoadedAnalysisConfig,
) -> tuple[UltralyticsDetector, MMPoseTopDownEstimator | None]:
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
    return detector, pose_estimator


def build_analysis_pipeline(
    config: LoadedAnalysisConfig,
    *,
    session_id: str,
    frame_loader: FrameLoader,
    model_pool: PersistentModelPool | None = None,
) -> VideoPosePipeline:
    cfg = config.config
    if model_pool is None:
        detector, pose_estimator = _build_models(config)
    else:
        model_pool.load()
        detector = model_pool.detector
        pose_estimator = model_pool.pose_estimator

    perception_model = PerceptionV1Model(
        detector,
        pose_estimator,
        person_confidence=cfg.detector.person_confidence,
        object_confidence=cfg.detector.object_confidence,
    )
    perception = MultiViewPerceptionAdapter(
        session_id=session_id,
        frame_loader=frame_loader,
        model=perception_model,
    )

    processors = []
    if cfg.calibration is not None:
        calibration = load_planar_calibration(config.resolve(cfg.calibration))
        processors.append(WorldProjectionProcessor(calibration))
        if cfg.identity.enabled:
            processors.append(
                MultiViewIdentityProcessor(
                    distance_threshold=cfg.identity.distance_threshold,
                    max_missed=cfg.identity.max_missed,
                )
            )

    if (
        cfg.triangulation.enabled
        and cfg.triangulation.calibration is not None
    ):
        perspective = load_perspective_calibration(
            config.resolve(cfg.triangulation.calibration)
        )
        processors.append(
            TriangulationProcessor(
                perspective,
                max_reprojection_rmse=(
                    cfg.triangulation.max_reprojection_rmse
                ),
            )
        )

    enrichers = []
    if cfg.zones is not None:
        zone_config = load_zones(config.resolve(cfg.zones))
        enrichers.append(ZoneRelationBuilder(zone_config.zones))

    enrichers.append(
        HumanObjectRelationBuilder(
            hold_ratio=cfg.relation.hold_ratio,
            near_ratio=cfg.relation.near_ratio,
            min_hold_px=cfg.relation.min_hold_px,
            min_near_px=cfg.relation.min_near_px,
            hold_frames=cfg.relation.hold_frames,
            free_frames=cfg.relation.free_frames,
        )
    )

    recognizers = [
        PickPlaceActionRecognizer(
            session_id,
            min_confidence=cfg.action_min_confidence,
        )
    ]
    if cfg.actions.tool_classes:
        recognizers.append(
            ToolOperationRecognizer(
                session_id,
                tool_classes=cfg.actions.tool_classes,
                operation_zones=cfg.actions.operation_zones or None,
                min_path_length=cfg.actions.tool_min_path_length,
                min_confidence=cfg.action_min_confidence,
            )
        )
    if cfg.actions.enable_zone_transitions:
        recognizers.append(
            ZoneTransitionRecognizer(
                session_id,
                entity_classes=cfg.actions.zone_entity_classes or None,
            )
        )
    if cfg.actions.inspect_zones:
        recognizers.append(
            DwellZoneActionRecognizer(
                session_id,
                action=ActionType.INSPECT,
                zones=cfg.actions.inspect_zones,
                entity_classes=cfg.actions.inspect_entity_classes or None,
                dwell_frames=cfg.actions.inspect_dwell_frames,
                min_confidence=cfg.action_min_confidence,
            )
        )

    return VideoPosePipeline(
        perception=perception,
        action_recognizer=CompositeActionRecognizer(recognizers),
        observation_processors=processors,
        observation_enrichers=enrichers,
    )


def build_rule_engine(config: LoadedAnalysisConfig) -> RuleEngine:
    return RuleEngine.from_yaml(config.resolve(config.config.rules))
