from __future__ import annotations

import shutil
from pathlib import Path

from .live_health import StorageHealthSnapshot
from .runtime_config import LoadedAnalysisConfig


def _nearest_existing_path(path: Path) -> Path:
    current = path.resolve(strict=False)
    while not current.exists():
        parent = current.parent
        if parent == current:
            return Path("/")
        current = parent
    return current


def sample_storage(
    name: str,
    path: str | Path,
) -> StorageHealthSnapshot:
    configured = Path(path).resolve(strict=False)
    probe = _nearest_existing_path(configured)
    usage = shutil.disk_usage(probe)
    free_ratio = (
        usage.free / usage.total
        if usage.total
        else 0.0
    )
    return StorageHealthSnapshot(
        name=name,
        configured_path=str(configured),
        probe_path=str(probe),
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        free_ratio=free_ratio,
    )


def sample_runtime_storage(
    config: LoadedAnalysisConfig,
    *,
    audit_root: str | Path,
) -> list[StorageHealthSnapshot]:
    output = [
        sample_storage(
            "audit",
            audit_root,
        )
    ]
    if config.config.evidence.enabled:
        output.append(
            sample_storage(
                "evidence",
                config.resolve(config.config.evidence.root),
            )
        )
    return output
