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


@pytest.mark.parametrize(
    "role",
    ["ADMIN", "ENGINEER", "SUPERVISOR", "REVIEWER", "AUDITOR"],
)
def test_evidence_read_roles(role: str) -> None:
    manager = _manager(role)
    principal = manager.authenticate_token("token")
    manager.require(principal, Permission.EVIDENCE_READ)


def test_operator_cannot_read_evidence() -> None:
    manager = _manager("OPERATOR")
    principal = manager.authenticate_token("token")
    with pytest.raises(AuthorizationError):
        manager.require(principal, Permission.EVIDENCE_READ)
