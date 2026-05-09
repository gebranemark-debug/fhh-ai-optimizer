"""Auth primitives: bcrypt password hashing, JWT issue/decode, FastAPI deps.

Reuses the SQLAlchemy engine / session factory from ``backend.postgres.db``
so the auth module shares one pool with the rest of the app.

Token format: HS256 JWT, 24h expiry, signed with ``JWT_SECRET`` env var.
Claims: ``sub`` (user UUID), ``email``, ``role``, ``exp``, ``iat``.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import (
    Boolean, DateTime, String, func, select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.postgres.db import Base, get_session_factory


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def _jwt_secret() -> str:
    """Read JWT_SECRET each call so tests can patch the env var."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # Fail loudly at decode/encode time rather than silently signing with
        # a default — prevents accidentally shipping with a guessable secret.
        raise RuntimeError(
            "JWT_SECRET env var is not set. Generate one with "
            "`python -c 'import secrets; print(secrets.token_urlsafe(48))'` "
            "and set it in Railway Variables."
        )
    return secret


# ---------------------------------------------------------------------------
# ORM model — mirrors app_schema.sql `app_users`
# ---------------------------------------------------------------------------

class AppUser(Base):
    __tablename__ = "app_users"

    id:             Mapped[uuid.UUID]      = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email:          Mapped[str]            = mapped_column(String(255), unique=True, nullable=False)
    password_hash:  Mapped[str]            = mapped_column(String(255), nullable=False)
    role:           Mapped[str]            = mapped_column(String(50), nullable=False)
    full_name:      Mapped[Optional[str]]  = mapped_column(String(255))
    is_active:      Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at:     Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT issue/decode
# ---------------------------------------------------------------------------

@dataclass
class TokenPayload:
    user_id: uuid.UUID
    email: str
    role: str


def create_access_token(user: AppUser) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    try:
        claims = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "token_expired", "message": "Token has expired.", "status": 401}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": "Could not validate credentials.", "status": 401}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenPayload(
        user_id=uuid.UUID(claims["sub"]),
        email=claims["email"],
        role=claims["role"],
    )


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def get_user_by_email(s: Session, email: str) -> Optional[AppUser]:
    return s.scalars(select(AppUser).where(AppUser.email == email.lower())).first()


def get_user_by_id(s: Session, user_id: uuid.UUID) -> Optional[AppUser]:
    return s.get(AppUser, user_id)


def count_users(s: Session) -> int:
    return int(s.scalar(select(func.count(AppUser.id))) or 0)


def create_user(
    s: Session,
    *,
    email: str,
    password: str,
    role: str,
    full_name: Optional[str] = None,
) -> AppUser:
    user = AppUser(
        id=uuid.uuid4(),
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        full_name=full_name,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    s.add(user)
    s.flush()
    return user


def touch_last_login(s: Session, user: AppUser) -> None:
    user.last_login_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

# tokenUrl is informational; we don't use OAuth2 password flow over the form
# encoding, but FastAPI's Bearer extraction is exposed via this class.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


def get_current_user(token: str = Depends(oauth2_scheme)) -> AppUser:
    payload = decode_access_token(token)
    factory = get_session_factory()
    s = factory()
    try:
        user = get_user_by_id(s, payload.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "invalid_token", "message": "User not found or disabled.", "status": 401}},
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Detach so the caller doesn't have to manage session lifetime.
        s.expunge(user)
        return user
    finally:
        s.close()


def require_role(*allowed_roles: str):
    """Dependency factory: ``Depends(require_role('admin'))``."""
    allowed = set(allowed_roles)

    def _dep(user: AppUser = Depends(get_current_user)) -> AppUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {
                    "code": "forbidden",
                    "message": f"Role '{user.role}' is not permitted for this action.",
                    "status": 403,
                }},
            )
        return user

    return _dep
