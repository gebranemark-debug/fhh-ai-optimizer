"""User-written maintenance entries (Path C feature 2).

Public surface:
    router — FastAPI APIRouter mounted in api.py
"""

from backend.maintenance.router import router

__all__ = ["router"]
