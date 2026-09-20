from __future__ import annotations

import hashlib
import hmac
import json
import os
from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    SUPERVISOR = "SUPERVISOR"
    REVIEWER = "REVIEWER"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"


class Permission(StrEnum):
    RUNTIME_READ = "runtime:read"
    CAMERA_READ = "camera:read"
    SESSION_READ = "session:read"
    SESSION_START = "session:start"
    SESSION_CONTROL = "session:control"
    PERSISTENCE_READ = "persistence:read"
    METRICS_READ = "metrics:read"
    REALTIME_READ = "realtime:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.ENGINEER: frozenset(
        {
            Permission.RUNTIME_READ,
            Permission.CAMERA_READ,
            Permission.SESSION_READ,
            Permission.SESSION_START,
            Permission.SESSION_CONTROL,
            Permission.PERSISTENCE_READ,
            Permission.METRICS_READ,
            Permission.REALTIME_READ,
        }
    ),
    Role.SUPERVISOR: frozenset(
        {
            Permission.RUNTIME_READ,
            Permission.CAMERA_READ,
            Permission.SESSION_READ,
            Permission.SESSION_START,
            Permission.SESSION_CONTROL,
            Permission.REALTIME_READ,
        }
    ),
    Role.REVIEWER: frozenset(
        {
            Permission.RUNTIME_READ,
            Permission.CAMERA_READ,
            Permission.SESSION_READ,
            Permission.REALTIME_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.RUNTIME_READ,
            Permission.CAMERA_READ,
            Permission.SESSION_READ,
            Permission.SESSION_START,
            Permission.REALTIME_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.RUNTIME_READ,
            Permission.SESSION_READ,
            Permission.PERSISTENCE_READ,
            Permission.METRICS_READ,
        }
    ),
}


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class TokenRecord(BaseModel):
    subject: str
    role: Role
    token_sha256: str = Field(min_length=64, max_length=64)
    disabled: bool = False


class AuthPrincipal(BaseModel):
    subject: str
    role: Role
    permissions: set[Permission]


class AuthConfiguration(BaseModel):
    enabled: bool = False
    tokens: list[TokenRecord] = Field(default_factory=list)


def hash_token(token: str) -> str:
    if not token:
        raise ValueError("token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AuthManager:
    """Opaque bearer-token authentication with role-based permissions."""

    def __init__(self, configuration: AuthConfiguration) -> None:
        self.configuration = configuration
        self._records = [
            record
            for record in configuration.tokens
            if not record.disabled
        ]

    @classmethod
    def disabled(cls) -> AuthManager:
        return cls(AuthConfiguration(enabled=False))

    @classmethod
    def from_environment(
        cls,
        *,
        force_enabled: bool | None = None,
    ) -> AuthManager:
        enabled = (
            force_enabled
            if force_enabled is not None
            else _parse_bool(os.getenv("VIDEO_POSE_AUTH_ENABLED"))
        )
        raw = os.getenv("VIDEO_POSE_AUTH_TOKENS_JSON", "[]")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "VIDEO_POSE_AUTH_TOKENS_JSON must be valid JSON"
            ) from exc

        configuration = AuthConfiguration.model_validate(
            {
                "enabled": enabled,
                "tokens": payload,
            }
        )
        if enabled and not configuration.tokens:
            raise ValueError(
                "authentication is enabled but no token records are configured"
            )
        return cls(configuration)

    @property
    def enabled(self) -> bool:
        return self.configuration.enabled

    def authenticate_bearer(
        self,
        authorization: str | None,
    ) -> AuthPrincipal:
        if not self.enabled:
            return self._development_principal()

        if not authorization:
            raise AuthenticationError("missing Authorization header")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token.strip():
            raise AuthenticationError(
                "Authorization must use Bearer <token>"
            )
        return self.authenticate_token(token.strip())

    def authenticate_token(self, token: str | None) -> AuthPrincipal:
        if not self.enabled:
            return self._development_principal()
        if not token:
            raise AuthenticationError("missing access token")

        digest = hash_token(token)
        for record in self._records:
            if hmac.compare_digest(record.token_sha256, digest):
                return AuthPrincipal(
                    subject=record.subject,
                    role=record.role,
                    permissions=set(ROLE_PERMISSIONS[record.role]),
                )
        raise AuthenticationError("invalid access token")

    def require(
        self,
        principal: AuthPrincipal,
        permission: Permission,
    ) -> AuthPrincipal:
        if permission not in principal.permissions:
            raise AuthorizationError(
                f"permission denied: {permission.value}"
            )
        return principal

    def authorize_bearer(
        self,
        authorization: str | None,
        permission: Permission,
    ) -> AuthPrincipal:
        principal = self.authenticate_bearer(authorization)
        return self.require(principal, permission)

    def authorize_token(
        self,
        token: str | None,
        permission: Permission,
    ) -> AuthPrincipal:
        principal = self.authenticate_token(token)
        return self.require(principal, permission)

    @staticmethod
    def _development_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="development",
            role=Role.ADMIN,
            permissions=set(Permission),
        )
