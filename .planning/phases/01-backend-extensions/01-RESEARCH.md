# Phase 1: Backend Extensions - Research

**Researched:** 2026-03-05
**Domain:** FastAPI endpoint extensions -- process management, audio transcription, sleep prevention, video serving
**Confidence:** HIGH

## Summary

Phase 1 adds five new endpoint groups to the existing FastAPI application (`dashboard/web.py`): process management (start/stop/status for the detector subprocess), audio transcription (accept WebM, transcribe with faster-whisper, extract CNP/email), video serving with HTTP 206 range support, sleep prevention via wakepy, and a StaticFiles mount for serving the future Vite frontend build. All endpoints are backend-only and testable with curl before any JavaScript is written.

The existing codebase is well-structured for extension. The FastAPI app is created via `create_dashboard_app()` in `dashboard/web.py`, which accepts a `DashboardState` object and optional references to `webhook_sender` and `analyzer`. New endpoints should be added as separate modules under a new `api/` directory (not crammed into `web.py`), then included as APIRouters in the app factory. The detector (`main.py`) runs as a complete standalone process with its own signal handling -- the process manager must spawn it as a subprocess, not import it.

The critical discovery from this research is that **faster-whisper 1.2.1 bundles PyAV, which includes FFmpeg libraries internally**. System-level ffmpeg is NOT required for the transcription endpoint. The prior research blocker ("ffmpeg must be on PATH on Windows 11 mini PC") is resolved -- PyAV handles WebM/Opus decoding natively. The `model.transcribe()` method accepts file paths directly and PyAV decodes any format ffmpeg supports. This simplifies the transcription endpoint significantly: save the uploaded WebM to a temp file, pass the path to `model.transcribe()`, no subprocess ffmpeg conversion step needed.

**Primary recommendation:** Build three API modules (`api/process_manager.py`, `api/transcribe.py`, `api/sleep_guard.py`) as FastAPI APIRouters, integrated into the existing `create_dashboard_app()` factory. Add video range-request serving and StaticFiles mount directly in `web.py`. Install `faster-whisper` and `wakepy` into the active `.venv/`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-01 | FastAPI serves Vite-built frontend via StaticFiles mount | StaticFiles with `html=True` at "/" -- mount AFTER all API routes; requires `aiofiles` |
| BACK-02 | POST /api/process/start starts detector subprocess | `subprocess.Popen` with `sys.executable` and `main.py` path; module-level singleton process handle |
| BACK-03 | POST /api/process/stop stops detector subprocess (psutil tree kill on Windows) | `psutil.Process(pid).children(recursive=True)` then terminate+wait+kill; psutil 7.2.2 already installed |
| BACK-04 | GET /api/process/status returns detector process state | Poll `_detector_proc.poll()` -- None means running; also surface in WebSocket snapshot |
| BACK-05 | POST /api/transcribe accepts audio blob, transcribes with faster-whisper, returns text+CNP+email | faster-whisper 1.2.1 with PyAV -- no system ffmpeg needed; save WebM temp file, pass path to `model.transcribe()` |
| BACK-06 | GET /api/videos/:id serves video files with HTTP 206 range support | Custom endpoint with Range header parsing, Content-Range response, status 206; NOT StaticFiles (no range support in Chrome) |
| BACK-07 | POST /api/system/wake-lock activates wakepy sleep prevention | `wakepy.keep.presenting()` context manager entered programmatically; wakepy 1.0.0 |
| BACK-08 | POST /api/system/wake-lock/release deactivates wakepy sleep prevention | Exit the keep.presenting context manager; set global reference to None |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.6 (installed) | API framework | Already running the dashboard; extend, don't replace |
| psutil | 7.2.2 (installed) | Process tree kill on Windows | Reliable cross-platform process management; already in .venv |
| faster-whisper | 1.2.1 (to install) | Romanian speech-to-text | Bundles PyAV internally; no system ffmpeg needed; same version as existing controller.py |
| wakepy | 1.0.0 (to install) | OS-level sleep prevention | Cross-platform, no admin rights; wraps caffeinate (macOS) / SetThreadExecutionState (Windows) |
| python-multipart | 0.0.22 (installed) | Parse multipart audio uploads | Required by FastAPI UploadFile; already present |
| aiofiles | (to install) | Async file serving for StaticFiles | Implicit FastAPI StaticFiles dependency |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyAV (av) | auto (via faster-whisper) | Audio/video decoding | Automatically installed as faster-whisper dependency; handles WebM/Opus without system ffmpeg |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psutil tree kill | `subprocess.run(['taskkill', '/F', '/T', '/PID', pid])` | Windows-only; psutil is cross-platform and already installed |
| wakepy | Direct `caffeinate`/`SetThreadExecutionState` via subprocess/ctypes | More code, less testable, platform-specific branches |
| Custom range endpoint | FastAPI StaticFiles for videos | StaticFiles does NOT return 206 in Chrome -- browser cannot seek |
| Save WebM + ffmpeg convert + transcribe WAV | Save WebM and pass directly to faster-whisper | faster-whisper/PyAV handles WebM natively; no conversion step needed |

**Installation:**
```bash
# In .venv (the active virtual environment)
pip install faster-whisper==1.2.1 wakepy==1.0.0 aiofiles
```

## Architecture Patterns

### Recommended Project Structure (Phase 1 additions)
```
clinic-entrance-detector/
|-- api/                        # NEW: FastAPI extension modules
|   |-- __init__.py
|   |-- process_manager.py      # Subprocess start/stop/status for main.py
|   |-- transcribe.py           # /api/transcribe -- Whisper + CNP/email extraction
|   +-- sleep_guard.py          # /api/system/wake-lock -- wakepy wrapper
|-- dashboard/
|   +-- web.py                  # MODIFIED: include APIRouters, add video endpoint, StaticFiles mount
|-- video1.mp4 ... video8.mp4   # EXISTING: served by new /api/videos/:id endpoint
+-- .env                        # EXISTING: add VIDEO_DIR, WHISPER_MODEL, WHISPER_COMPUTE_TYPE
```

### Pattern 1: APIRouter Modules Included in App Factory

**What:** Each new endpoint group is a separate `APIRouter` in its own module under `api/`. The `create_dashboard_app()` factory in `web.py` includes them with `app.include_router()`.

**When to use:** Always for new API endpoints. Do not add routes directly to `web.py`.

**Example:**
```python
# api/process_manager.py
from fastapi import APIRouter
router = APIRouter(prefix="/api/process", tags=["process"])

@router.post("/start")
async def start():
    ...

# dashboard/web.py -- inside create_dashboard_app()
from api.process_manager import router as process_router
app.include_router(process_router)
```

### Pattern 2: Process Manager with Module-Level Singleton

**What:** A single `subprocess.Popen` handle stored at module level. The process manager provides `start_detector()`, `stop_detector()`, and `detector_status()` functions. The stop function uses psutil tree kill for reliable teardown on all platforms.

**When to use:** Always for the detector subprocess. Never use `multiprocessing.Process` (shares interpreter, complicates teardown). Never run detector in-process (blocks asyncio event loop).

**Example:**
```python
# api/process_manager.py
import subprocess, sys, platform
from pathlib import Path
import psutil

_detector_proc: subprocess.Popen | None = None
_project_root = Path(__file__).resolve().parent.parent

def start_detector() -> dict:
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

def stop_detector() -> dict:
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
```

### Pattern 3: Transcription with Direct PyAV Decoding

**What:** Save the uploaded WebM blob to a temp file. Pass the file path directly to `faster_whisper.WhisperModel.transcribe()`. PyAV (bundled with faster-whisper) decodes WebM/Opus natively. No system ffmpeg needed. Extract CNP and email from the transcribed text using the same regex patterns from `controller.py`.

**When to use:** Always for the transcription endpoint. Do not shell out to ffmpeg.

**Example:**
```python
# api/transcribe.py
import re, tempfile, os
from fastapi import APIRouter, UploadFile, File
from faster_whisper import WhisperModel

router = APIRouter(tags=["transcribe"])
_model: WhisperModel | None = None

def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel("medium", compute_type="int8")
    return _model

def extract_cnp(text: str) -> str | None:
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 13:
        return digits[:13]
    return None

def extract_email(text: str) -> str | None:
    # Port from controller.py -- normalize Romanian speech artifacts
    attempt = text.lower()
    attempt = re.sub(r"\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)", r".\2", attempt)
    attempt = re.sub(
        r"\s*(arond|arong|aroon|arun|arung|at|et|ad|@|a run|a rung)\s*",
        "@", attempt
    )
    if "@" in attempt and "." in attempt.split("@")[-1]:
        parts = attempt.split("@")
        local = parts[0].replace(" ", "").rstrip(".")
        domain = parts[1].replace(" ", "").lstrip(".")
        result = local + "@" + domain
        result = re.sub(r"[^a-z0-9@._\-]", "", result)
        return result
    return None

@router.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    model = get_model()

    suffix = ".webm"
    if audio.content_type and "wav" in audio.content_type:
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        segments, _ = model.transcribe(tmp_path, language="ro", vad_filter=True)
        text = " ".join(s.text for s in segments).strip()
    finally:
        os.unlink(tmp_path)

    cnp = extract_cnp(text)
    email = extract_email(text)

    return {"text": text, "cnp": cnp, "email": email}
```

### Pattern 4: Video Serving with HTTP 206 Range Requests

**What:** A custom GET endpoint that parses the `Range` header, reads the requested byte range from the video file, and returns a `Response` with status 206, `Content-Range`, and `Accept-Ranges: bytes` headers. FastAPI's `StaticFiles` does NOT support range requests properly in Chrome (returns 200 instead of 206, breaking seek).

**When to use:** Always for video file serving. Do not use StaticFiles for the video files.

**Example:**
```python
# In dashboard/web.py or api/video_server.py
from pathlib import Path
from fastapi import Request, Response, HTTPException

VIDEO_DIR = Path(__file__).resolve().parent.parent  # project root where video1-8.mp4 live

ALLOWED_VIDEOS = {f"video{i}.mp4" for i in range(1, 9)}

@app.get("/api/videos/{filename}")
async def serve_video(filename: str, request: Request):
    if filename not in ALLOWED_VIDEOS:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = VIDEO_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Video file missing")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header is None:
        # Full file response
        return Response(
            content=file_path.read_bytes(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    # Parse range
    range_str = range_header.replace("bytes=", "")
    parts = range_str.split("-")
    start = int(parts[0]) if parts[0] else 0
    end = int(parts[1]) if parts[1] else min(start + 1024 * 1024, file_size - 1)
    end = min(end, file_size - 1)

    if start > end or start < 0 or end >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

    length = end - start + 1
    with open(file_path, "rb") as f:
        f.seek(start)
        data = f.read(length)

    return Response(
        content=data,
        status_code=206,
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )
```

### Pattern 5: Sleep Guard with Programmatic Context Manager Control

**What:** The wakepy `keep.presenting()` context manager is entered manually via `__enter__()` on activation and exited via `__exit__()` on deactivation. A module-level variable holds the active context.

**When to use:** Always for sleep prevention. The context manager pattern ensures clean resource management.

**Example:**
```python
# api/sleep_guard.py
from fastapi import APIRouter
from wakepy import keep

router = APIRouter(prefix="/api/system", tags=["system"])
_keep_ctx = None
_mode = None

@router.post("/wake-lock")
async def activate_wake_lock():
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
    global _keep_ctx, _mode
    if _keep_ctx is None:
        return {"status": "already_inactive"}

    _keep_ctx.__exit__(None, None, None)
    _keep_ctx = None
    _mode = None
    return {"status": "inactive"}
```

### Anti-Patterns to Avoid

- **Running detector in-process:** Never import main.py and call run() directly. YOLO inference is CPU-bound and blocks asyncio.
- **Using `process.terminate()` alone:** Leaves camera-holding orphan processes on Windows. Always use psutil tree kill.
- **Shelling out to system ffmpeg for audio conversion:** faster-whisper uses PyAV which bundles ffmpeg libraries. Direct `model.transcribe(file_path)` works with WebM.
- **Using StaticFiles for video serving:** Chrome requires HTTP 206 for seeking. StaticFiles returns 200, breaking video seek.
- **Loading Whisper model per request:** Load once at startup or first request, reuse for all transcriptions. Each load takes 10-30 seconds and consumes significant memory.
- **Adding routes directly to web.py:** Use separate APIRouter modules under `api/` for clean separation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform sleep prevention | Custom caffeinate/SetThreadExecutionState code | `wakepy.keep.presenting()` | Platform detection, error handling, cleanup are deceptively complex |
| Process tree kill on Windows | Manual PID walking with ctypes | `psutil.Process(pid).children(recursive=True)` + terminate/kill | Windows process trees have edge cases (zombie children, access denied) |
| WebM/Opus audio decoding | Shell out to ffmpeg subprocess | `faster_whisper.WhisperModel.transcribe(path)` via PyAV | PyAV is bundled; eliminates system dependency and subprocess overhead |
| Romanian CNP extraction | Custom NLP pipeline | Regex: `re.sub(r"[^0-9]", "", text)` then check length >= 13 | CNP is always 13 digits; Whisper outputs them as words, regex strips non-digits |
| Email extraction from speech | Custom NLP pipeline | Port regex from controller.py (lines 213-233) | Handles Romanian speech artifacts ("arond" -> "@", "punct" -> ".") |

**Key insight:** The existing `controller.py` already has working, production-tested CNP and email extraction logic. Port it, do not redesign it.

## Common Pitfalls

### Pitfall 1: Subprocess Zombies on Windows (Camera Lock)
**What goes wrong:** `process.terminate()` kills only the root Python process on Windows. OpenCV and BoT-SORT child threads keep running, holding the webcam. Next start fails with "camera already in use."
**Why it happens:** Windows does not propagate SIGTERM to child processes.
**How to avoid:** Use `psutil.Process(pid).children(recursive=True)` to enumerate all descendants. Terminate all, wait 5 seconds, force-kill survivors. Test 5 consecutive start/stop cycles.
**Warning signs:** "Camera already in use" error on second start; multiple python.exe processes in Task Manager after stop.

### Pitfall 2: Whisper Model Loaded Per Request
**What goes wrong:** Each POST to `/api/transcribe` loads the Whisper model from disk (10-30 seconds), then processes audio. Total latency is 15-40 seconds instead of 3-5 seconds.
**Why it happens:** Developer creates WhisperModel inside the endpoint function instead of at module/startup level.
**How to avoid:** Lazy-load the model on first request, store in a module-level global. All subsequent requests reuse the same model instance. The model is thread-safe for sequential calls.
**Warning signs:** First transcription takes 30+ seconds; subsequent ones also take 30+ seconds.

### Pitfall 3: StaticFiles for Video (No Range Support)
**What goes wrong:** Video files served via `StaticFiles` mount return HTTP 200 for all requests. Chrome's `<video>` element requires HTTP 206 Partial Content for seeking. Without it, videos play but cannot be seeked -- scrubbing jumps back to the start.
**Why it happens:** Starlette's StaticFiles implementation does not parse Range headers or return 206 responses.
**How to avoid:** Build a custom endpoint that parses the Range header, reads the requested byte range, and returns Response with status_code=206, Content-Range header, and Accept-Ranges: bytes.
**Warning signs:** Video plays from start but seeking/scrubbing fails; browser console shows no 206 responses for video requests.

### Pitfall 4: WebSocket Snapshot Missing New Fields
**What goes wrong:** Frontend (Phase 2+) expects `detector_running` and `workflow_phase` fields in the WebSocket snapshot. If these are not added to `DashboardState.snapshot()` in Phase 1, the frontend integration breaks silently (fields are `undefined` in JS).
**Why it happens:** New API modules are built but the shared state object is not extended.
**How to avoid:** Add `detector_running` (from process_manager) and `wake_lock_active` (from sleep_guard) to `DashboardState.snapshot()` output in this phase.
**Warning signs:** Frontend shows "undefined" or missing values for system status fields.

### Pitfall 5: Wrong Working Directory for Detector Subprocess
**What goes wrong:** `subprocess.Popen` inherits the CWD of the FastAPI process. If FastAPI is started from a different directory, `main.py` cannot find `.env`, `calibration.json`, YOLO model files, or video files.
**Why it happens:** `main.py` uses relative paths (via `config.py`'s `load_dotenv()`).
**How to avoid:** Explicitly set `cwd=str(project_root)` in the Popen call, where project_root is derived from the process_manager module's own file path.
**Warning signs:** Detector subprocess exits immediately with "Model not found" or "calibration.json not found" errors.

## Code Examples

### Complete Process Manager Module

```python
# api/process_manager.py
# Source: Verified patterns from psutil docs + existing main.py structure
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

_detector_proc: subprocess.Popen | None = None
_project_root = Path(__file__).resolve().parent.parent


def start_detector() -> dict[str, Any]:
    """Start the detector subprocess (main.py)."""
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
    """Stop the detector subprocess with process tree kill."""
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
    """Return current detector process state."""
    if _detector_proc is None:
        return {"running": False, "pid": None, "exit_code": None}

    poll = _detector_proc.poll()
    if poll is not None:
        return {"running": False, "pid": _detector_proc.pid, "exit_code": poll}

    return {"running": True, "pid": _detector_proc.pid, "exit_code": None}
```

### CNP/Email Extraction (Ported from controller.py)

```python
# Source: controller.py lines 195-233 -- production-tested patterns
import re

def extract_cnp(text: str) -> str | None:
    """Extract Romanian CNP (13 digits) from transcribed speech."""
    digits_only = re.sub(r"[^0-9]", "", text)
    if len(digits_only) >= 13:
        return digits_only[:13]
    if len(digits_only) >= 10:
        return digits_only  # Partial CNP for user confirmation
    return None

def extract_email(text: str) -> str | None:
    """Extract email from Romanian speech transcription.

    Handles common Whisper misrecognitions:
    - "arond/arong/arun/at" -> "@"
    - "punct/dot" -> "."
    """
    attempt = text.lower()
    attempt = re.sub(
        r"\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)",
        r".\2",
        attempt,
    )
    attempt = re.sub(
        r"\s*(arond|arong|aroon|arun|arung|at|et|ad|@|a run|a rung)\s*",
        "@",
        attempt,
    )
    if "@" in attempt and "." in attempt.split("@")[-1]:
        parts = attempt.split("@")
        local = parts[0].replace(" ", "").rstrip(".")
        domain = parts[1].replace(" ", "").lstrip(".") if len(parts) > 1 else ""
        result = local + "@" + domain
        result = re.sub(r"[^a-z0-9@._\\-]", "", result)
        return result
    return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| System ffmpeg for audio conversion | PyAV bundled with faster-whisper | faster-whisper 0.9+ | No system ffmpeg dependency; simplifies deployment |
| `process.terminate()` for subprocess cleanup | psutil tree kill | Always needed on Windows | Prevents camera lock after stop/start cycles |
| Flask on port 5050 for webhook receiver | FastAPI unified on port 8080 | This phase | Single server, no CORS, single process to manage |
| VLC RC socket for video playback | HTML5 video served via API | This phase | No external process, browser-native playback |
| sounddevice for mic capture | Browser MediaRecorder (Phase 4) + backend transcription | This phase (backend) | Backend receives audio blob, transcribes -- no hardware dependency on server |
| wakepy 0.x API | wakepy 1.0.0 with `keep.presenting()` | October 2024 | New API: decorator/context manager pattern; `Mode` object with `.active` check |

**Deprecated/outdated:**
- controller.py Flask webhook listener on port 5050 -- replaced by FastAPI endpoint
- sounddevice mic recording on server -- replaced by browser-side recording in Phase 4
- VLC RC socket interface -- replaced by HTML5 video in Phase 3
- Manual ffmpeg subprocess for audio conversion -- eliminated by PyAV

## Open Questions

1. **Whisper model lazy-load vs startup-load**
   - What we know: Loading the medium model takes 10-30 seconds. In controller.py it loads at import time (blocking).
   - What's unclear: Whether to load at FastAPI startup (delays server readiness) or lazy-load on first transcription request.
   - Recommendation: Lazy-load on first request. FastAPI needs to be responsive for process management immediately. The first transcription will be slower, but subsequent ones are fast. Add a `GET /api/transcribe/status` endpoint so frontend can check if the model is loaded.

2. **DashboardState extension scope**
   - What we know: The WebSocket snapshot needs `detector_running` and `wake_lock_active` fields for Phase 2+ frontend.
   - What's unclear: Whether to add these to DashboardState dataclass or keep process_manager/sleep_guard state separate.
   - Recommendation: Add a `detector_running: bool` field to DashboardState. For wake_lock, add it to the snapshot() method by calling sleep_guard's status function. Keep the source of truth in the respective modules, but surface it in the WebSocket.

3. **Video file location**
   - What we know: Video files (video1-8.mp4) are currently in the project root directory.
   - What's unclear: Whether to add a VIDEO_DIR env var or hardcode the project root.
   - Recommendation: Use a `VIDEO_DIR` env var with default falling back to project root. Add to `config.py` Settings and `.env`.

## Sources

### Primary (HIGH confidence)
- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) - v1.2.1, PyAV bundles FFmpeg, no system ffmpeg needed
- [wakepy readthedocs 1.0.0](https://wakepy.readthedocs.io/stable/) - `keep.presenting()` API, Mode.active check
- [wakepy user guide](https://wakepy.readthedocs.io/stable/user-guide.html) - Context manager and decorator patterns
- [psutil documentation](https://psutil.readthedocs.io/en/latest/) - Process.children(recursive=True), wait_procs, kill
- [FastAPI StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/) - StaticFiles mount with html=True
- [FastAPI video streaming discussion #7718](https://github.com/fastapi/fastapi/discussions/7718) - HTTP 206 range request implementation
- [FastAPI video streaming guide](https://stribny.name/posts/fastapi-video/) - Range header parsing, Content-Range response
- Existing codebase: `dashboard/web.py` (FastAPI app factory), `controller.py` (CNP/email extraction logic), `main.py` (detector entry point)

### Secondary (MEDIUM confidence)
- [FastAPI subprocess discussion #7442](https://github.com/fastapi/fastapi/discussions/7442) - subprocess.Popen patterns with FastAPI
- [psutil PyPI](https://pypi.org/project/psutil/) - v7.2.2 (already installed in .venv)
- [FastAPI serving React frontend](https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/) - StaticFiles with html=True for SPA routing

### Tertiary (LOW confidence)
- None -- all findings verified against official docs or existing codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified against PyPI/official docs; versions confirmed in existing venvs
- Architecture: HIGH - patterns derived from existing `dashboard/web.py` code structure and FastAPI official docs
- Pitfalls: HIGH - subprocess zombie issue verified against psutil docs; StaticFiles range limitation confirmed by FastAPI discussion #7718; PyAV/ffmpeg finding verified against faster-whisper PyPI page

**Key correction from prior research:** The blocker "ffmpeg must be on PATH on Windows 11 mini PC" (STATE.md) is RESOLVED. faster-whisper 1.2.1 uses PyAV which bundles FFmpeg libraries internally. System ffmpeg is not needed for the transcription endpoint.

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable libraries, no fast-moving components)
