"""Process management API for the detector subprocess.

Provides start/stop/status endpoints that manage main.py as a subprocess.
Uses psutil tree kill for reliable cross-platform process teardown.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter

_detector_proc: subprocess.Popen | None = None
_project_root = Path(__file__).resolve().parent.parent

router = APIRouter(prefix="/api/process", tags=["process"])


def start_detector() -> dict[str, Any]:
    """Start the detector subprocess (main.py).

    Returns {"status": "started", "pid": int} on success,
    or {"status": "already_running", "pid": int} if already active.
    """
    global _detector_proc
    if _detector_proc is not None and _detector_proc.poll() is None:
        return {"status": "already_running", "pid": _detector_proc.pid}

    _detector_proc = subprocess.Popen(
        [sys.executable, str(_project_root / "main.py")],
        cwd=str(_project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {"status": "started", "pid": _detector_proc.pid}


def stop_detector() -> dict[str, Any]:
    """Stop the detector subprocess with process tree kill.

    Uses psutil to enumerate and terminate all child processes
    before the parent, then force-kills any survivors after timeout.
    """
    global _detector_proc
    if _detector_proc is None or _detector_proc.poll() is not None:
        _detector_proc = None
        return {"status": "not_running"}

    pid = _detector_proc.pid
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        parent.terminate()
        gone, alive = psutil.wait_procs([parent] + children, timeout=5)
        for p in alive:
            p.kill()
    except psutil.NoSuchProcess:
        pass

    _detector_proc = None
    return {"status": "stopped", "pid": pid}


def detector_status() -> dict[str, Any]:
    """Return current detector process state.

    Returns running status, PID, and exit code (if process has exited).
    """
    if _detector_proc is None:
        return {"running": False, "pid": None, "exit_code": None}

    poll = _detector_proc.poll()
    if poll is not None:
        return {"running": False, "pid": _detector_proc.pid, "exit_code": poll}

    return {"running": True, "pid": _detector_proc.pid, "exit_code": None}


@router.post("/start")
async def api_start() -> dict[str, Any]:
    """POST /api/process/start -- start the detector subprocess."""
    return start_detector()


@router.post("/stop")
async def api_stop() -> dict[str, Any]:
    """POST /api/process/stop -- stop the detector subprocess."""
    return stop_detector()


@router.get("/status")
async def api_status() -> dict[str, Any]:
    """GET /api/process/status -- get detector process state."""
    return detector_status()
