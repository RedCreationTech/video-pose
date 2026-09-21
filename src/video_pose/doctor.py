from __future__ import annotations

import importlib.util
import shutil
import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from .camera_model import (
    load_control_points,
    validate_calibration_health,
)
from .gstreamer_capture import opencv_has_gstreamer
from .model_release import (
    load_model_release_manifest,
    verify_model_release_manifest,
)
from .native_gstreamer_capture import inspect_native_gstreamer
from .perspective import load_perspective_calibration
from .runtime_config import (
    CaptureBackend,
    LoadedAnalysisConfig,
    load_analysis_config,
)


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DoctorCheck(BaseModel):
    name: str
    status: CheckStatus
    required: bool
    detail: str


class DoctorReport(BaseModel):
    checks: list[DoctorCheck]

    @property
    def passed(self) -> bool:
        return not any(
            check.required and check.status == CheckStatus.FAIL
            for check in self.checks
        )


def _module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _binary_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _path_check(
    name: str,
    path: Path,
    *,
    required: bool = True,
) -> DoctorCheck:
    if path.exists():
        return DoctorCheck(
            name=name,
            status=CheckStatus.PASS,
            required=required,
            detail=str(path),
        )
    return DoctorCheck(
        name=name,
        status=CheckStatus.FAIL if required else CheckStatus.WARN,
        required=required,
        detail=f"missing: {path}",
    )


def _cuda_check(config: LoadedAnalysisConfig) -> DoctorCheck:
    devices = [config.config.detector.device]
    if config.config.pose is not None and config.config.pose.enabled:
        devices.append(config.config.pose.device)
    needs_cuda = any(
        isinstance(device, str) and device.lower().startswith("cuda")
        for device in devices
    )
    if not needs_cuda:
        return DoctorCheck(
            name="cuda",
            status=CheckStatus.PASS,
            required=False,
            detail="CUDA device not requested by config",
        )
    if not _module_exists("torch"):
        return DoctorCheck(
            name="cuda",
            status=CheckStatus.FAIL,
            required=True,
            detail="config requests CUDA but torch is not installed",
        )
    try:
        import torch
    except Exception as exc:
        return DoctorCheck(
            name="cuda",
            status=CheckStatus.FAIL,
            required=True,
            detail=f"torch import failed: {exc}",
        )
    available = bool(torch.cuda.is_available())
    detail = "CUDA available" if available else "torch.cuda.is_available() is false"
    return DoctorCheck(
        name="cuda",
        status=CheckStatus.PASS if available else CheckStatus.FAIL,
        required=True,
        detail=detail,
    )


def _gstreamer_check(config: LoadedAnalysisConfig) -> DoctorCheck | None:
    backend = config.config.live.backend
    if backend == CaptureBackend.GSTREAMER_OPENCV:
        try:
            import cv2
        except ImportError:
            return DoctorCheck(
                name="opencv-gstreamer",
                status=CheckStatus.FAIL,
                required=True,
                detail="cv2 is not installed",
            )

        supported = opencv_has_gstreamer(cv2)
        return DoctorCheck(
            name="opencv-gstreamer",
            status=(
                CheckStatus.PASS
                if supported
                else CheckStatus.FAIL
            ),
            required=True,
            detail=(
                "OpenCV GStreamer support is enabled"
                if supported
                else "OpenCV build reports GStreamer=NO"
            ),
        )

    if backend != CaptureBackend.GSTREAMER_NATIVE:
        return None

    try:
        detail = inspect_native_gstreamer(
            require_reference_timestamp=(
                config.config.live.native_timestamp_source.value
                == "reference"
            )
        )
    except Exception as exc:
        return DoctorCheck(
            name="native-gstreamer",
            status=CheckStatus.FAIL,
            required=True,
            detail=str(exc),
        )
    return DoctorCheck(
        name="native-gstreamer",
        status=CheckStatus.PASS,
        required=True,
        detail=detail,
    )


def _calibration_health_check(
    config: LoadedAnalysisConfig,
) -> DoctorCheck | None:
    health = config.config.calibration_health
    if not health.enabled:
        return None

    calibration_value = (
        health.calibration
        or config.config.triangulation.calibration
    )
    if calibration_value is None:
        return DoctorCheck(
            name="calibration-health",
            status=CheckStatus.FAIL,
            required=True,
            detail="perspective calibration is not configured",
        )
    if health.control_points is None:
        return DoctorCheck(
            name="calibration-health",
            status=CheckStatus.FAIL,
            required=True,
            detail="calibration control points are not configured",
        )

    try:
        profile = load_perspective_calibration(
            config.resolve(calibration_value)
        )
        controls = load_control_points(
            config.resolve(health.control_points)
        )
        report = validate_calibration_health(
            profile,
            controls,
            max_rmse=health.max_rmse,
        )
    except Exception as exc:
        return DoctorCheck(
            name="calibration-health",
            status=CheckStatus.FAIL,
            required=True,
            detail=str(exc),
        )

    detail = ", ".join(
        (
            f"{camera.camera_id}:"
            f"rmse={camera.rmse:.6f}:"
            f"{'PASS' if camera.passed else 'FAIL'}"
        )
        for camera in report.cameras
    )
    return DoctorCheck(
        name="calibration-health",
        status=(
            CheckStatus.PASS
            if report.passed
            else CheckStatus.FAIL
        ),
        required=True,
        detail=detail or "no camera health results",
    )


def _model_release_check(
    config: LoadedAnalysisConfig,
) -> DoctorCheck | None:
    release = config.config.model_release
    if not release.enabled:
        return None
    if release.manifest is None:
        return DoctorCheck(
            name="model-release",
            status=CheckStatus.FAIL,
            required=True,
            detail="model release manifest is not configured",
        )

    path = config.resolve(release.manifest)
    try:
        manifest = load_model_release_manifest(path)
        verification = verify_model_release_manifest(manifest)
    except Exception as exc:
        return DoctorCheck(
            name="model-release",
            status=CheckStatus.FAIL,
            required=True,
            detail=str(exc),
        )

    failures = [
        item
        for item in verification.artifacts
        if not item.passed
    ]
    detail = (
        f"release_id={manifest.release_id}, "
        f"artifacts={len(manifest.artifacts)}"
    )
    if failures:
        detail += "; " + "; ".join(
            (
                f"{item.name}:"
                f"exists={item.exists}:"
                f"size={item.size_matches}:"
                f"sha256={item.sha256_matches}"
            )
            for item in failures
        )
    return DoctorCheck(
        name="model-release",
        status=(
            CheckStatus.PASS
            if verification.passed
            else CheckStatus.FAIL
        ),
        required=True,
        detail=detail,
    )


def build_doctor_report(
    config_path: str | Path,
    *,
    module_exists: Callable[[str], bool] | None = None,
    binary_exists: Callable[[str], bool] | None = None,
    include_cuda: bool = True,
) -> DoctorReport:
    module_probe = module_exists or _module_exists
    binary_probe = binary_exists or _binary_exists
    loaded = load_analysis_config(config_path)
    cfg = loaded.config
    checks: list[DoctorCheck] = []

    version_ok = sys.version_info >= (3, 11)
    checks.append(
        DoctorCheck(
            name="python",
            status=CheckStatus.PASS if version_ok else CheckStatus.FAIL,
            required=True,
            detail=sys.version.split()[0],
        )
    )

    for binary in ("ffprobe", "ffmpeg"):
        exists = binary_probe(binary)
        checks.append(
            DoctorCheck(
                name=f"binary:{binary}",
                status=CheckStatus.PASS if exists else CheckStatus.FAIL,
                required=True,
                detail="available" if exists else "not found in PATH",
            )
        )

    required_modules = ["pydantic", "yaml", "cv2", "ultralytics"]
    if cfg.pose is not None and cfg.pose.enabled:
        required_modules.extend(
            ["mmpose", "mmengine", "mmcv"]
        )
    for module in required_modules:
        exists = module_probe(module)
        checks.append(
            DoctorCheck(
                name=f"python-module:{module}",
                status=CheckStatus.PASS if exists else CheckStatus.FAIL,
                required=True,
                detail="available" if exists else "not installed",
            )
        )

    gstreamer = _gstreamer_check(loaded)
    if gstreamer is not None:
        checks.append(gstreamer)

    assets: list[tuple[str, str | None]] = [
        ("manifest", cfg.manifest),
        ("rules", cfg.rules),
        ("calibration", cfg.calibration),
        ("zones", cfg.zones),
        ("detector-weights", cfg.detector.weights),
    ]
    if cfg.pose is not None and cfg.pose.enabled:
        assets.extend(
            [
                ("pose-config", cfg.pose.config),
                ("pose-checkpoint", cfg.pose.checkpoint),
            ]
        )
    if cfg.triangulation.enabled:
        assets.append(
            ("perspective-calibration", cfg.triangulation.calibration)
        )
    if cfg.calibration_health.enabled:
        assets.extend(
            [
                (
                    "calibration-health-profile",
                    (
                        cfg.calibration_health.calibration
                        or cfg.triangulation.calibration
                    ),
                ),
                (
                    "calibration-control-points",
                    cfg.calibration_health.control_points,
                ),
            ]
        )

    for name, value in assets:
        if value is None:
            if name == "perspective-calibration":
                checks.append(
                    DoctorCheck(
                        name=name,
                        status=CheckStatus.FAIL,
                        required=True,
                        detail="triangulation is enabled but calibration is unset",
                    )
                )
            continue
        checks.append(_path_check(name, loaded.resolve(value)))

    calibration_health = _calibration_health_check(loaded)
    if calibration_health is not None:
        checks.append(calibration_health)

    model_release = _model_release_check(loaded)
    if model_release is not None:
        checks.append(model_release)

    if include_cuda:
        checks.append(_cuda_check(loaded))

    return DoctorReport(checks=checks)
