from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from .model_release import load_model_release_manifest
from .runtime_config import (
    LoadedAnalysisConfig,
    effective_capture_timestamp_source,
)
from .video_manifest import ReplayManifest


class RuntimeFingerprint(BaseModel):
    capture_backend: str
    timestamp_source: str
    sync_tolerance_ms: float
    camera_clock_offsets_ms: dict[str, float] = Field(
        default_factory=dict
    )
    config_sha256: str | None = None
    manifest_sha256: str | None = None
    rules_sha256: str | None = None
    zones_sha256: str | None = None
    planar_calibration_sha256: str | None = None
    perspective_calibration_sha256: str | None = None
    calibration_health_profile_sha256: str | None = None
    calibration_control_points_sha256: str | None = None
    pose_config_sha256: str | None = None
    model_release_id: str | None = None
    model_release_manifest_sha256: str | None = None
    model_artifact_sha256: dict[str, str] = Field(
        default_factory=dict
    )


def sha256_file(path: str | Path) -> str | None:
    target = Path(path)
    if not target.is_file():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_config_path(
    config: LoadedAnalysisConfig,
    value: str | None,
) -> str | None:
    if value is None:
        return None
    return sha256_file(config.resolve(value))


def build_runtime_fingerprint(
    config: LoadedAnalysisConfig,
    manifest: ReplayManifest,
) -> RuntimeFingerprint:
    cfg = config.config
    perspective = (
        cfg.triangulation.calibration
        if cfg.triangulation.enabled
        else None
    )
    health_profile = (
        cfg.calibration_health.calibration
        or cfg.triangulation.calibration
        if cfg.calibration_health.enabled
        else None
    )
    model_release_id = None
    model_artifact_sha256: dict[str, str] = {}
    model_release_manifest_sha256 = None
    if (
        cfg.model_release.enabled
        and cfg.model_release.manifest is not None
    ):
        release_path = config.resolve(
            cfg.model_release.manifest
        )
        model_release_manifest_sha256 = sha256_file(
            release_path
        )
        if release_path.is_file():
            release = load_model_release_manifest(
                release_path
            )
            model_release_id = release.release_id
            model_artifact_sha256 = {
                artifact.name: artifact.sha256
                for artifact in release.artifacts
            }

    return RuntimeFingerprint(
        capture_backend=cfg.live.backend.value,
        timestamp_source=effective_capture_timestamp_source(
            cfg.live
        ).value,
        sync_tolerance_ms=float(
            getattr(manifest, "sync_tolerance_ms", 0.0)
        ),
        camera_clock_offsets_ms={
            camera.camera_id: camera.clock_offset_ms
            for camera in getattr(manifest, "cameras", [])
            if getattr(camera, "enabled", True)
        },
        config_sha256=sha256_file(config.path),
        manifest_sha256=_hash_config_path(
            config,
            cfg.manifest,
        ),
        rules_sha256=_hash_config_path(
            config,
            cfg.rules,
        ),
        zones_sha256=_hash_config_path(
            config,
            cfg.zones,
        ),
        planar_calibration_sha256=_hash_config_path(
            config,
            cfg.calibration,
        ),
        perspective_calibration_sha256=_hash_config_path(
            config,
            perspective,
        ),
        calibration_health_profile_sha256=_hash_config_path(
            config,
            health_profile,
        ),
        calibration_control_points_sha256=_hash_config_path(
            config,
            (
                cfg.calibration_health.control_points
                if cfg.calibration_health.enabled
                else None
            ),
        ),
        pose_config_sha256=_hash_config_path(
            config,
            (
                cfg.pose.config
                if cfg.pose is not None and cfg.pose.enabled
                else None
            ),
        ),
        model_release_id=model_release_id,
        model_release_manifest_sha256=(
            model_release_manifest_sha256
        ),
        model_artifact_sha256=model_artifact_sha256,
    )
