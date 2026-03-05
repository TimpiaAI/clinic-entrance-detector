"""Sleep guard API for wake-lock activation/deactivation.

Provides endpoints to prevent the kiosk PC from sleeping via wakepy.
Uses keep.presenting() context manager entered/exited programmatically.
"""

from __future__ import annotations

from fastapi import APIRouter
from wakepy import keep

router = APIRouter(prefix="/api/system", tags=["system"])

_keep_ctx = None
_mode = None


def wake_lock_status() -> dict:
    """Return current wake lock status (called by DashboardState.snapshot)."""
    return {"active": False}
