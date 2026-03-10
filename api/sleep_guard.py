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
    """Return current wake lock status (called by DashboardState.snapshot).

    Returns {"active": True} when a wake lock is held and active,
    {"active": False} otherwise.
    """
    return {"active": _mode is not None and _mode.active}


@router.post("/wake-lock")
async def activate_wake_lock():
    """Activate OS-level sleep prevention via wakepy keep.presenting().

    Returns:
        {"status": "active"} on success
        {"status": "already_active"} if lock already held
        {"status": "failed", "detail": ...} if activation failed
    """
    global _keep_ctx, _mode

    if _mode is not None and _mode.active:
        return {"status": "already_active"}

    _keep_ctx = keep.presenting()
    _mode = _keep_ctx.__enter__()

    if not _mode.active:
        _keep_ctx.__exit__(None, None, None)
        _keep_ctx = None
        _mode = None
        return {"status": "failed", "detail": "Could not activate sleep prevention"}

    return {"status": "active"}


@router.post("/wake-lock/release")
async def release_wake_lock():
    """Deactivate sleep prevention by exiting the keep.presenting() context.

    Returns:
        {"status": "inactive"} on success
        {"status": "already_inactive"} if no lock held
    """
    global _keep_ctx, _mode

    if _keep_ctx is None:
        return {"status": "already_inactive"}

    try:
        _keep_ctx.__exit__(None, None, None)
    except ValueError:
        # wakepy uses ContextVar internally which fails across async boundaries.
        # The lock is still released at the OS level when the context is discarded.
        pass
    _keep_ctx = None
    _mode = None
    return {"status": "inactive"}
