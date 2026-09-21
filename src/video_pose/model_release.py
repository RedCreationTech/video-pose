from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from .runtime_config import LoadedAnalysisConfig


class ModelReleaseArtifact(BaseModel):
    name: str
    role: str
    path: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)


class ModelReleaseManifest(BaseModel):
    schema_version: int = 1
    release_id: str = Field(min_length=1, max_length=256)
    created_at: str
    artifacts: list[ModelReleaseArtifact]

    @model_validator(mode="after")
    def unique_artifact_names(self) -> ModelReleaseManifest:
        names = [artifact.name for artifact in self.artifacts]
        if len(names) != len(set(names)):
            raise ValueError("model release artifact names must be unique")
        return self


class ModelArtifactVerification(BaseModel):
    name: str
    role: str
    path: str
    exists: bool
    size_matches: bool
    sha256_matches: bool
    actual_size_bytes: int | None = None
    actual_sha256: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.exists
            and self.size_matches
            and self.sha256_matches
        )


class ModelReleaseVerification(BaseModel):
    release_id: str
    artifacts: list[ModelArtifactVerification]

    @property
    def passed(self) -> bool:
        return bool(self.artifacts) and all(
            artifact.passed for artifact in self.artifacts
        )


def sha256_path(path: str | Path) -> str:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(target)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(
    *,
    name: str,
    role: str,
    path: Path,
) -> ModelReleaseArtifact:
    if not path.is_file():
        raise FileNotFoundError(path)
    return ModelReleaseArtifact(
        name=name,
        role=role,
        path=str(path),
        size_bytes=path.stat().st_size,
        sha256=sha256_path(path),
    )


def build_model_release_manifest(
    config: LoadedAnalysisConfig,
    *,
    release_id: str,
) -> ModelReleaseManifest:
    artifacts = [
        _artifact(
            name="detector",
            role="detector_weights",
            path=config.resolve(
                config.config.detector.weights
            ),
        )
    ]
    pose = config.config.pose
    if pose is not None and pose.enabled:
        artifacts.append(
            _artifact(
                name="pose",
                role="pose_checkpoint",
                path=config.resolve(pose.checkpoint),
            )
        )
    return ModelReleaseManifest(
        release_id=release_id,
        created_at=datetime.now(UTC).isoformat(),
        artifacts=artifacts,
    )


def write_model_release_manifest(
    manifest: ModelReleaseManifest,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_model_release_manifest(
    path: str | Path,
) -> ModelReleaseManifest:
    return ModelReleaseManifest.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def verify_model_release_manifest(
    manifest: ModelReleaseManifest,
) -> ModelReleaseVerification:
    results: list[ModelArtifactVerification] = []
    for artifact in manifest.artifacts:
        path = Path(artifact.path)
        if not path.is_file():
            results.append(
                ModelArtifactVerification(
                    name=artifact.name,
                    role=artifact.role,
                    path=artifact.path,
                    exists=False,
                    size_matches=False,
                    sha256_matches=False,
                )
            )
            continue

        actual_size = path.stat().st_size
        actual_sha = sha256_path(path)
        results.append(
            ModelArtifactVerification(
                name=artifact.name,
                role=artifact.role,
                path=artifact.path,
                exists=True,
                size_matches=actual_size == artifact.size_bytes,
                sha256_matches=actual_sha == artifact.sha256,
                actual_size_bytes=actual_size,
                actual_sha256=actual_sha,
            )
        )
    return ModelReleaseVerification(
        release_id=manifest.release_id,
        artifacts=results,
    )
