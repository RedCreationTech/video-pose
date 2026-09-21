from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

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
    )
