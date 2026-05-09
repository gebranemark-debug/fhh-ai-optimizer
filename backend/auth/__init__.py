"""Authentication + RBAC module for the FHH AI Optimizer backend (Path C).

Public surface:
    router          — FastAPI APIRouter mounted under /auth in api.py
    get_current_user — dependency returning the AppUser for the bearer token
    require_role    — dependency factory (e.g. require_role("admin"))
"""

from backend.auth.router import router
from backend.auth.security import (
    AppUser,
    get_current_user,
    require_role,
)

__all__ = ["router", "AppUser", "get_current_user", "require_role"]
