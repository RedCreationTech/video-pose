from video_pose.runtime_config import load_analysis_config
from video_pose.runtime_identity import build_runtime_release_identity
from video_pose.video_manifest import load_manifest


def test_release_identity_is_stable_and_git_sensitive(
    monkeypatch,
) -> None:
    loaded = load_analysis_config("configs/offline-demo.yaml")
    manifest = load_manifest(
        loaded.resolve(loaded.config.manifest)
    )

    monkeypatch.setenv(
        "VIDEO_POSE_GIT_SHA",
        "a" * 40,
    )
    monkeypatch.setenv(
        "VIDEO_POSE_IMAGE_DIGEST",
        "sha256:" + "b" * 64,
    )
    first = build_runtime_release_identity(
        loaded,
        manifest,
    )
    second = build_runtime_release_identity(
        loaded,
        manifest,
    )
    assert first.release_fingerprint == second.release_fingerprint
    assert first.git_sha == "a" * 40
    assert first.image_digest == "sha256:" + "b" * 64
    assert len(first.release_fingerprint) == 64

    monkeypatch.setenv(
        "VIDEO_POSE_GIT_SHA",
        "c" * 40,
    )
    changed = build_runtime_release_identity(
        loaded,
        manifest,
    )
    assert changed.release_fingerprint != first.release_fingerprint
