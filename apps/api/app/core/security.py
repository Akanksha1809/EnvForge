"""Password hashing and JWT issuance/verification.

Kept isolated from route handlers so auth logic has one place to audit, and
so services (e.g. RBAC checks) can depend on `decode_token` without importing
FastAPI routing concerns.
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# bcrypt's underlying algorithm silently ignores bytes past 72 — truncate
# explicitly so behavior is well-defined rather than library-dependent.
_MAX_PASSWORD_BYTES = 72


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    pass


def hash_password(plain_password: str) -> str:
    truncated = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def create_token(
    subject: str, token_type: TokenType, extra_claims: dict[str, Any] | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_delta = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == TokenType.ACCESS
        else timedelta(minutes=settings.refresh_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if expected_type and payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"expected token type {expected_type.value!r}")
    return payload
