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


def test_engineer_can_repair_persistence() -> None:
    principal = _manager("ENGINEER").authenticate_token("token")
    _manager("ENGINEER").require(
        principal,
        Permission.PERSISTENCE_REPAIR,
    )


@pytest.mark.parametrize("role", ["SUPERVISOR", "REVIEWER", "OPERATOR", "AUDITOR"])
def test_non_engineer_roles_cannot_repair_persistence(role: str) -> None:
    manager = _manager(role)
    principal = manager.authenticate_token("token")
    with pytest.raises(AuthorizationError):
        manager.require(principal, Permission.PERSISTENCE_REPAIR)
