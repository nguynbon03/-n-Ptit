"""Authentication helpers for server-side admin and learner sessions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException

from mongo_store import get_store

_ALGORITHM = "HS256"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _secret() -> str:
    value = os.getenv("JWT_SECRET_KEY", "").strip()
    if not value:
        raise RuntimeError("JWT_SECRET_KEY is required for authentication")
    return value


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_text, digest_text = encoded.split("$")
        if scheme != "scrypt":
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        digest = hashlib.scrypt(password.encode(), salt=decode(salt_text), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(digest, decode(digest_text))
    except (ValueError, TypeError):
        return False


def create_access_token(user: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "learner"),
        "iat": now,
        "exp": now + timedelta(hours=int(os.getenv("JWT_EXPIRE_HOURS", "12"))),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "email": user["email"], "role": user.get("role", "learner"), "status": user.get("status", "active")}


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(authorization[7:], _secret(), algorithms=[_ALGORITHM])
    except (jwt.InvalidTokenError, RuntimeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_store().find_user_by_email(str(payload.get("email", "")))
    if not user or user.get("status", "active") != "active" or user.get("id") != payload.get("sub"):
        raise HTTPException(status_code=401, detail="User session is no longer valid")
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return _public_user(user)
