"""
services/auth.py
JWT token management and password hashing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from config.settings import settings

# ── Password hashing ─────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────

def create_access_token(user_id: uuid.UUID, workspace_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """Returns (token_string, expires_at)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expire


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises JWTError on failure.
    Always validate the 'type' claim at the call site.
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def decode_access_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    return payload
