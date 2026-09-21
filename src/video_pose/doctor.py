from __future__ import annotations

import importlib.util
import shutil
import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from .gstreamer_capture import opencv_has_gstreamer
from .native_gstreamer_capture import inspect_native_gstreamer
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

    if include_cuda:
        checks.append(_cuda_check(loaded))

    return DoctorReport(checks=checks)
