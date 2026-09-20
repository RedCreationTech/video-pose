import pytest

from video_pose.auth import (
    AuthConfiguration,
    AuthManager,
    AuthorizationError,
    Permission,
    hash_token,
)


def _manager(role: str) -> AuthManager:
    return AuthManager(
        AuthConfiguration.model_validate(
            {
                "enabled": True,
                "tokens": [
                    {
                        "subject": role.lower(),
                        "role": role,
                        "token_sha256": hash_token("token"),
                    }
                ],
            }
        )
    )


@pytest.mark.parametrize("role", ["REVIEWER", "SUPERVISOR", "ADMIN"])
def test_review_roles_have_review_permission(role: str) -> None:
    manager = _manager(role)
    principal = manager.authenticate_token("token")
    manager.require(principal, Permission.VIOLATION_REVIEW)


@pytest.mark.parametrize("role", ["OPERATOR", "AUDITOR", "ENGINEER"])
def test_non_review_roles_are_denied(role: str) -> None:
    manager = _manager(role)
    principal = manager.authenticate_token("token")
    with pytest.raises(AuthorizationError):
        manager.require(principal, Permission.VIOLATION_REVIEW)
