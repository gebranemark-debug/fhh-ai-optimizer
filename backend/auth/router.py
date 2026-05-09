"""Auth router: POST /auth/register, POST /auth/login, GET /auth/me.

First registration auto-promotes to ``admin`` so an empty database can
bootstrap. Subsequent registrations require an existing admin's bearer
token (passed via the standard Authorization: Bearer ... header).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from backend.postgres.db import session_scope
from backend.auth.security import (
    AppUser,
    count_users,
    create_access_token,
    create_user,
    decode_access_token,
    get_current_user,
    get_user_by_email,
    require_role,
    touch_last_login,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, pattern="^(admin|operator)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


def _user_to_response(user: AppUser) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _bearer_token_from_header(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    parts = header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Create a new user.

    - First user ever: auto-promoted to ``admin``, no auth required.
    - Subsequent users: caller must present a bearer token for an active admin.
    """
    with session_scope() as s:
        existing_count = count_users(s)

        if existing_count == 0:
            role = "admin"
        else:
            token = _bearer_token_from_header(authorization)
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": {
                        "code": "auth_required",
                        "message": "Bearer token required to register additional users.",
                        "status": 401,
                    }},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            payload = decode_access_token(token)
            if payload.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {
                        "code": "forbidden",
                        "message": "Only admins can register new users.",
                        "status": 403,
                    }},
                )
            role = body.role or "operator"

        if get_user_by_email(s, body.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {
                    "code": "email_taken",
                    "message": f"A user with email '{body.email}' already exists.",
                    "status": 409,
                }},
            )

        user = create_user(
            s,
            email=body.email,
            password=body.password,
            role=role,
            full_name=body.full_name,
        )
        return _user_to_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    with session_scope() as s:
        user = get_user_by_email(s, body.email)
        if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
            # Single error message to avoid email enumeration.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {
                    "code": "invalid_credentials",
                    "message": "Email or password is incorrect.",
                    "status": 401,
                }},
            )
        touch_last_login(s, user)
        token = create_access_token(user)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=24 * 60 * 60,
            user=_user_to_response(user),
        )


@router.get("/me", response_model=UserResponse)
def me(user: AppUser = Depends(get_current_user)):
    return _user_to_response(user)


@router.get("/_admin-ping", response_model=dict, include_in_schema=False)
def admin_ping(user: AppUser = Depends(require_role("admin"))) -> dict:
    """Smoke-test endpoint for require_role; not part of the public contract."""
    return {"ok": True, "user_id": str(user.id), "role": user.role}
