import json

import pytest

from video_pose.auth import (
    AuthConfiguration,
    AuthManager,
    AuthenticationError,
    AuthorizationError,
    Permission,
    Role,
    hash_token,
)


def test_auth_manager_accepts_hashed_bearer_token() -> None:
    manager = AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "supervisor-1",
                        "role": "SUPERVISOR",
                        "token_sha256": hash_token("secret-token"),
                    }
                ],
            }
        )
    )
    principal = manager.authorize_bearer(
        "Bearer secret-token",
        Permission.SESSION_START,
    )
    assert principal.subject == "supervisor-1"
    assert principal.role == Role.SUPERVISOR


def test_auth_manager_rejects_invalid_token() -> None:
    manager = AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "admin",
                        "role": "ADMIN",
                        "token_sha256": hash_token("good"),
                    }
                ],
            }
        )
    )
    with pytest.raises(AuthenticationError):
        manager.authenticate_bearer("Bearer bad")


def test_supervisor_cannot_read_metrics() -> None:
    manager = AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": "supervisor",
                        "role": "SUPERVISOR",
                        "token_sha256": hash_token("token"),
                    }
                ],
            }
        )
    )
    principal = manager.authenticate_token("token")
    with pytest.raises(AuthorizationError):
        manager.require(principal, Permission.METRICS_READ)


def test_disabled_mode_returns_development_admin() -> None:
    manager = AuthManager.disabled()
    principal = manager.authorize_bearer(
        None,
        Permission.METRICS_READ,
    )
    assert principal.role == Role.ADMIN


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO_POSE_AUTH_ENABLED", "1")
    monkeypatch.setenv(
        "VIDEO_POSE_AUTH_TOKENS_JSON",
        json.dumps(
            [
                {
                    "subject": "reviewer",
                    "role": "REVIEWER",
                    "token_sha256": hash_token("review-token"),
                }
            ]
        ),
    )
    manager = AuthManager.from_environment()
    assert manager.enabled is True
    assert (
        manager.authenticate_token("review-token").subject
        == "reviewer"
    )
