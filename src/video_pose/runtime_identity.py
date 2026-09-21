from __future__ import annotations

import hashlib
import json
import os
from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel

from .runtime_config import LoadedAnalysisConfig
from .runtime_fingerprint import (
    RuntimeFingerprint,
    build_runtime_fingerprint,
)
from .video_manifest import ReplayManifest


class RuntimeReleaseIdentity(BaseModel):
    application_version: str
    git_sha: str
    image_digest: str | None = None
    release_fingerprint: str
    runtime_fingerprint: RuntimeFingerprint


def _application_version() -> str:
    try:
        return version("video-pose")
    except PackageNotFoundError:
        return "unknown"


def _canonical_release_fingerprint(
    *,
    application_version: str,
    git_sha: str,
    image_digest: str | None,
    runtime_fingerprint: RuntimeFingerprint,
) -> str:
    payload = {
        "application_version": application_version,
        "git_sha": git_sha,
        "image_digest": image_digest,
        "runtime_fingerprint": runtime_fingerprint.model_dump(
            mode="json"
        ),
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def build_runtime_release_identity(
    config: LoadedAnalysisConfig,
    manifest: ReplayManifest,
) -> RuntimeReleaseIdentity:
    application_version = _application_version()
    git_sha = os.getenv(
        "VIDEO_POSE_GIT_SHA",
        "unknown",
    ).strip() or "unknown"
    image_digest = (
        os.getenv("VIDEO_POSE_IMAGE_DIGEST", "").strip()
        or None
    )
    runtime_fingerprint = build_runtime_fingerprint(
        config,
        manifest,
    )
    release_fingerprint = _canonical_release_fingerprint(
        application_version=application_version,
        git_sha=git_sha,
        image_digest=image_digest,
        runtime_fingerprint=runtime_fingerprint,
    )
    return RuntimeReleaseIdentity(
        application_version=application_version,
        git_sha=git_sha,
        image_digest=image_digest,
        release_fingerprint=release_fingerprint,
        runtime_fingerprint=runtime_fingerprint,
    )
