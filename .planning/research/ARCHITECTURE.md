# Architecture Patterns

**Domain:** Kiosk web platform + Python detection backend (clinic entrance)
**Researched:** 2026-03-05
**Confidence:** HIGH

---

## Context: Architecture Shift

The prior milestone architecture (2026-03-04) used python-mpv + pytransitions — a pure-Python process
controlling a desktop video player. This milestone replaces that approach with:

- **Vite frontend** running in a kiosk browser window
- **FastAPI backend** extended with process management, transcription, and sleep prevention
- Browser as the presentation layer (video, audio, UI)
- Python as the control and inference layer (detection, Whisper, OS commands)

The detection pipeline (VideoStream → PersonTracker → EntryAnalyzer → WebhookSender) is **unchanged**.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BROWSER (Kiosk Mode)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │  Detection   │  │  Video       │  │  Audio     │  │  System  │  │
│  │  Feed View   │  │  Overlay     │  │  Recorder  │  │  Status  │  │
│  │  <img> MJPEG │  │  <video>     │  │  Web Audio │  │  Panel   │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘  │
│         │                 │                 │               │        │
│  ┌──────┴─────────────────┴─────────────────┴───────────────┴──────┐ │
│  │              App State (vanilla JS, event-driven)               │ │
│  │        WebSocket handler / fetch API / keyboard shortcuts       │ │
│  └───────────────────────────────────────────────────────────────-─┘ │
└──────────────────────┬──────────────────────────────────────────────┘
                       │  HTTP / WebSocket  (localhost:8080)
┌──────────────────────┴──────────────────────────────────────────────┐
│                   FASTAPI BACKEND (main process)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │  /video_feed │  │  /ws         │  │  /api/     │  │ /trigger │  │
│  │  MJPEG stream│  │  state push  │  │  process   │  │ webhook  │  │
│  │              │  │  (0.5s tick) │  │  mgmt      │  │ endpoint │  │
│  └──────────────┘  └──────────────┘  └────┬───────┘  └────┬─────┘  │
│                                           │               │         │
│  ┌──────────────────────────────────────  │  ─────────────┴──────┐  │
│  │  DashboardState (thread-safe shared   │  state object)        │  │
│  └──────────────────────────────────────────────────────────────-┘  │
│                                                                       │
│  ┌────────────────┐   ┌──────────────┐   ┌─────────────────────┐    │
│  │ DetectorProcess│   │ WhisperEngine│   │ SleepGuard          │    │
│  │ subprocess.Popen   │ (in-process) │   │ (OS commands)       │    │
│  │ manages main.py│   │ /api/        │   │ caffeinate/powercfg │    │
│  └────────────────┘   │ transcribe   │   └─────────────────────┘    │
│                        └──────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │   DETECTOR SUBPROCESS (main.py)  │
              │  VideoStream → PersonTracker      │
              │  → EntryAnalyzer → DashboardState │
              │  → WebhookSender                  │
              └──────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Boundary |
|-----------|---------------|----------|
| **Detection Feed View** | Shows `<img>` tag pointed at `/video_feed` (MJPEG) | Browser only, read-only |
| **Video Overlay** | `<video>` element covering full viewport; triggered by workflow state | Browser only |
| **Audio Recorder** | Web Audio API / MediaRecorder; captures mic, POSTs blob to `/api/transcribe` | Browser only |
| **App State** | Single JS object holding workflow phase, transcript results, system status; drives all DOM updates | Browser only |
| **WebSocket Handler** | Subscribes to `/ws`; updates App State on each tick | Browser ↔ FastAPI |
| **MJPEG Stream** | `/video_feed` endpoint; JPEG boundary stream from `DashboardState.frame_jpeg` | FastAPI → Browser |
| **WebSocket Server** | `/ws` endpoint; sends `DashboardState.snapshot()` every 0.5s | FastAPI → Browser |
| **Process Manager** | `POST /api/process/start` and `POST /api/process/stop`; spawns/kills `main.py` as subprocess | FastAPI internal |
| **WhisperEngine** | Loads `faster-whisper` model once at startup; `POST /api/transcribe` accepts audio blob, returns text | FastAPI internal |
| **SleepGuard** | `POST /api/sleep/prevent` and `POST /api/sleep/allow`; delegates to `caffeinate` (macOS) or `SetThreadExecutionState` / `powercfg` (Windows) | FastAPI internal |
| **Trigger Endpoint** | `POST /trigger`; receives webhook from detector, pushes `person_entered` event to all WebSocket clients | FastAPI → Browser |
| **DashboardState** | Thread-safe shared object; written by detector loop (or subprocess pipe), read by all FastAPI endpoints | FastAPI internal |

---

## Recommended Project Structure

```
clinic-entrance-detector/
├── main.py                    # Existing: detector entry point (unchanged)
├── controller.py              # Replaced by Vite frontend + FastAPI extensions
├── config.py                  # Existing (unchanged)
│
├── dashboard/
│   ├── web.py                 # Existing: extend with new endpoints
│   └── templates/             # Keep for fallback; Vite replaces these in prod
│
├── api/                       # New: FastAPI extension modules
│   ├── __init__.py
│   ├── process_manager.py     # Subprocess start/stop for main.py
│   ├── transcribe.py          # Whisper endpoint (/api/transcribe)
│   └── sleep_guard.py         # OS sleep prevention (/api/sleep/*)
│
├── frontend/                  # New: Vite project root
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js            # Entry point; wires all modules
│       ├── state.js           # App state object + mutation functions
│       ├── ws.js              # WebSocket connection + reconnect logic
│       ├── workflow.js        # Kiosk workflow state machine (JS)
│       ├── video.js           # HTML5 video overlay control
│       ├── audio.js           # MediaRecorder + /api/transcribe pipeline
│       ├── shortcuts.js       # Keyboard shortcut bindings
│       ├── ui.js              # DOM update functions (no logic)
│       └── style.css          # Fullscreen kiosk layout
│
└── videos/                    # video1.mp4 ... video8.mp4 (served by FastAPI /static)
```

### Structure Rationale

- **api/**: New API endpoints are isolated modules, not crammed into `dashboard/web.py`. Each module owns one concern (process, transcription, sleep).
- **frontend/src/**: Flat module structure. No subfolder nesting — this is a kiosk app, not a multi-page SPA. Each file is a named concern.
- **state.js**: Single source of truth for app state prevents state scattered across DOM attributes.
- **workflow.js**: Kiosk workflow logic (which video plays next, when to record) is separate from video.js and audio.js, mirroring the backend state machine design.
- **videos/**: Served as FastAPI `StaticFiles`. No need for a CDN or separate server.

---

## Architectural Patterns

### Pattern 1: MJPEG Stream via img Tag

**What:** Browser displays detection feed by setting `<img src="/video_feed">`. The backend streams multipart JPEG over HTTP. The img tag handles the streaming natively — no JS needed for the display itself.

**When to use:** Always. Do not use canvas-based decoders or JavaScript MJPEG parsers for this. The native img approach is simpler, lighter, and already working in the existing dashboard.

**Trade-offs:** The MJPEG connection is a persistent HTTP request. On browser reload, the img reconnects automatically. The feed is always visible; the video overlay sits above it using CSS z-index stacking.

```javascript
// No JS needed for display — just a static src attribute
// <img id="detection-feed" src="/video_feed" />

// To toggle visibility without breaking the MJPEG connection:
function toggleFeed(visible) {
  document.getElementById('detection-feed').style.opacity = visible ? '1' : '0';
  // Do NOT set src to '' — that terminates the MJPEG connection.
  // Use opacity or visibility instead.
}
```

### Pattern 2: Video Overlay via CSS Stacking

**What:** The `<video>` element is positioned absolutely over the detection feed using CSS. It is hidden (opacity: 0, pointer-events: none) by default and made visible only during kiosk workflow phases. The container element (not the video element itself) is made fullscreen.

**When to use:** Always for video playback. Never call the browser Fullscreen API on the video element directly — it breaks overlay compositing.

**Trade-offs:** Requires CSS discipline. The text overlay (marquee replacement) is a `<div>` inside the same container, above the video.

```css
#kiosk-container {
  position: fixed;
  inset: 0;
  background: #000;
}

#detection-feed {
  width: 100%;
  height: 100%;
  object-fit: contain;
  position: absolute;
  z-index: 1;
}

#instructional-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  position: absolute;
  z-index: 2;
  opacity: 0;
  transition: opacity 0.3s;
}

#text-overlay {
  position: absolute;
  bottom: 5%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  /* text styling */
}
```

```javascript
// workflow.js
function playVideo(src, onEnded) {
  const el = document.getElementById('instructional-video');
  el.src = src;
  el.onended = onEnded;
  el.style.opacity = '1';
  el.play();
}

function hideVideo() {
  const el = document.getElementById('instructional-video');
  el.style.opacity = '0';
  el.pause();
  el.src = '';
}
```

### Pattern 3: Audio Capture + Backend Transcription

**What:** `MediaRecorder` captures mic audio as a WebM/Opus blob. When recording stops, the blob is POSTed to `/api/transcribe` as `multipart/form-data`. The FastAPI endpoint saves it, runs faster-whisper, and returns JSON with the transcript text.

**When to use:** Always prefer this over real-time WebSocket audio streaming for this use case. The workflow always records a fixed duration (10 seconds) and then transcribes — batch mode is simpler, more reliable, and sufficient for 10-second clips.

**Trade-offs:** There is a ~1-3 second latency after recording ends before transcript returns. This is acceptable and matches the existing `sounddevice`-based approach latency. Real-time streaming would add complexity with no benefit for fixed-duration clips.

```javascript
// audio.js
async function recordAndTranscribe(durationMs = 10000) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
  const chunks = [];

  recorder.ondataavailable = e => chunks.push(e.data);
  recorder.start();

  await new Promise(resolve => setTimeout(resolve, durationMs));
  recorder.stop();
  await new Promise(resolve => (recorder.onstop = resolve));

  stream.getTracks().forEach(t => t.stop());

  const blob = new Blob(chunks, { type: 'audio/webm' });
  const form = new FormData();
  form.append('audio', blob, 'recording.webm');
  form.append('language', 'ro');

  const res = await fetch('/api/transcribe', { method: 'POST', body: form });
  return (await res.json()).text;
}
```

```python
# api/transcribe.py
from fastapi import APIRouter, UploadFile, File, Form
import tempfile, subprocess

router = APIRouter()

@router.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("ro")):
    # Save webm, convert to wav, transcribe
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(await audio.read())
        webm_path = tmp.name
    wav_path = webm_path.replace(".webm", ".wav")
    subprocess.run(["ffmpeg", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path], check=True)
    segments, _ = whisper_model.transcribe(wav_path, language=language, vad_filter=True)
    text = " ".join(s.text for s in segments).strip()
    return {"text": text}
```

### Pattern 4: Process Management via FastAPI

**What:** FastAPI holds a `subprocess.Popen` handle to the detector process (`main.py`). The `/api/process/start` endpoint spawns it; `/api/process/stop` sends SIGTERM and waits. The WebSocket state includes `detector_running: bool` so the browser reflects process state.

**When to use:** This approach is correct for a single-process detector on a local kiosk. Do not use multiprocessing.Process — it shares the interpreter and complicates teardown. A subprocess is isolated.

**Trade-offs:** The FastAPI server must outlive the detector. If FastAPI crashes, the detector keeps running (which is desirable — detection continues independently). The frontend must handle the case where the WebSocket disconnects.

```python
# api/process_manager.py
import subprocess, signal, sys
from pathlib import Path

_detector_proc: subprocess.Popen | None = None

def start_detector() -> bool:
    global _detector_proc
    if _detector_proc and _detector_proc.poll() is None:
        return False  # already running
    _detector_proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent.parent / "main.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True

def stop_detector() -> bool:
    global _detector_proc
    if _detector_proc is None or _detector_proc.poll() is not None:
        return False
    _detector_proc.send_signal(signal.SIGTERM)
    try:
        _detector_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _detector_proc.kill()
    _detector_proc = None
    return True

def detector_running() -> bool:
    return _detector_proc is not None and _detector_proc.poll() is None
```

### Pattern 5: Sleep Prevention via Backend OS Commands

**What:** The browser cannot call OS sleep prevention APIs directly. Instead, the frontend calls `POST /api/sleep/prevent` when the operator activates the system, and `POST /api/sleep/allow` when they stop it. The FastAPI endpoint runs `caffeinate -d` (macOS) or calls `SetThreadExecutionState` via ctypes (Windows). The `wakepy` library wraps both platforms.

**When to use:** Use `wakepy` as the primary implementation. It handles Windows and macOS without per-platform branches in application code.

**Trade-offs:** `wakepy` is a dependency with no Python sub-dependencies on Windows/macOS. The alternative (direct ctypes for Windows + subprocess for macOS) is ~15 lines but harder to test. `wakepy` is the right abstraction here.

```python
# api/sleep_guard.py
from wakepy import keep
from fastapi import APIRouter

router = APIRouter()
_keep_ctx = None

@router.post("/api/sleep/prevent")
async def prevent_sleep():
    global _keep_ctx
    if _keep_ctx is None:
        _keep_ctx = keep.presenting()
        _keep_ctx.__enter__()
    return {"status": "active"}

@router.post("/api/sleep/allow")
async def allow_sleep():
    global _keep_ctx
    if _keep_ctx is not None:
        _keep_ctx.__exit__(None, None, None)
        _keep_ctx = None
    return {"status": "inactive"}
```

### Pattern 6: Kiosk Browser Launch

**What:** The FastAPI server also serves the Vite build as static files. A launcher script opens Chrome/Chromium with `--kiosk` pointing at `http://localhost:8080`. The frontend is a plain SPA that works in all contexts.

**When to use:** Production deployment. Development uses Vite dev server with `npm run dev` and normal browser mode.

**Trade-offs:** Chrome `--kiosk` is cross-platform (same flag on Windows and macOS). Edge also supports `--kiosk`. The `--no-default-browser-check --no-first-run --disable-infobars` flags prevent startup dialogs.

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --kiosk --no-default-browser-check --no-first-run \
  --disable-infobars --user-data-dir=/tmp/kiosk-profile \
  http://localhost:8080

# Windows (PowerShell)
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList `
  "--kiosk", "--no-default-browser-check", "--no-first-run", `
  "--disable-infobars", "--user-data-dir=C:\temp\kiosk-profile", `
  "http://localhost:8080"
```

---

## Data Flow

### Flow 1: Person Enters Clinic (Happy Path)

```
[Camera] → [VideoStream.read()] → [PersonTracker.track()]
    → [EntryAnalyzer.update()] → [EntryEvent: person_entered]
    → [WebhookSender.submit()] → POST /trigger (FastAPI endpoint)
    → [DashboardState.push_event()]
    → [WebSocket /ws sends updated snapshot]
    → [Browser ws.js receives {event_log: [{event: "person_entered", ...}]}]
    → [workflow.js detects person_entered event]
    → [video.js plays video2.mp4 (greeting)]
    → [video.onended] → [video.js plays video3.mp4 (ask name)]
    → [video.onended] → [audio.js starts MediaRecorder for 10s]
    → [audio.js POSTs blob to /api/transcribe]
    → [FastAPI: ffmpeg converts webm→wav, faster-whisper transcribes]
    → [Returns {text: "Ion Ionescu"}]
    → [workflow.js stores name, shows text overlay, plays next video]
    → ... (repeat for CNP, email)
    → [video.js plays video4.mp4 (farewell)]
    → [video.onended] → [workflow.js returns to IDLE state]
    → [video.js shows detection feed again]
```

### Flow 2: Operator Activates System

```
[Keyboard: Space or F1]
    → [shortcuts.js captures keydown]
    → [POST /api/process/start]
    → [process_manager.py spawns main.py subprocess]
    → [POST /api/sleep/prevent]
    → [sleep_guard.py activates wakepy context]
    → [WebSocket begins receiving detection data]
    → [<img src="/video_feed"> connects, MJPEG stream starts]
    → [ui.js shows "SISTEMA ACTIV" status]
```

### Flow 3: Audio Recording Sequence

```
[workflow.js signals: start recording]
    → [audio.js: navigator.mediaDevices.getUserMedia({audio: true})]
    → [MediaRecorder.start()]
    → [10 second timer]
    → [MediaRecorder.stop()]
    → [ondataavailable: chunks collected]
    → [Blob assembled (audio/webm)]
    → [FormData: audio=blob, language=ro]
    → [POST /api/transcribe]
    → [FastAPI: saves webm to tmp dir]
    → [ffmpeg -i input.webm -ar 16000 -ac 1 output.wav]
    → [faster-whisper: transcribe(wav, language="ro", vad_filter=True)]
    → [text extraction + CNP/email pattern matching (Python side)]
    → [Response: {text: "1234567890123", type: "cnp"}]
    → [workflow.js stores result, triggers next phase]
```

### Flow 4: WebSocket State Sync

```
[DashboardState updated every frame by detector loop]
    → [FastAPI /ws sends snapshot() every 0.5s]
    → [Browser ws.js receives JSON]
    → [ws.js dispatches to App State]
    → [App State compares: new events in event_log?]
    → [If yes: workflow.js.onPersonEntered()]
    → [ui.js updates: FPS, active tracks, webhook status, uptime]
```

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Direction | Notes |
|----------|---------------|-----------|-------|
| Browser ↔ FastAPI (video) | HTTP MJPEG stream | Server → Browser | Persistent HTTP connection; do NOT reassign `img.src` unnecessarily |
| Browser ↔ FastAPI (state) | WebSocket JSON | Server → Browser | Browser must implement reconnect logic (exponential backoff) |
| Browser → FastAPI (audio) | HTTP POST multipart | Browser → Server | Batch after recording; no streaming WebSocket needed |
| Browser → FastAPI (commands) | HTTP POST JSON | Browser → Server | Start/stop detector, prevent sleep |
| FastAPI → Detector | subprocess.Popen | FastAPI → OS | Detector runs as child process; SIGTERM for graceful stop |
| FastAPI ↔ DashboardState | In-process threading.Lock | Both directions | Detector loop writes; API endpoints read |
| Detector → FastAPI | DashboardState (shared) | Detector → State object | Works because detector runs in same Python process if not subprocess — or via IPC if subprocess |
| FastAPI → Browser (events) | WebSocket push | Server → Browser | `person_entered` events appear in `event_log` in state snapshot |

**Critical note on DetectorProcess IPC:** When the detector runs as a subprocess (not the same Python process), it cannot write to `DashboardState` directly. The trigger webhook endpoint (`POST /trigger`) is the bridge — the subprocess already sends webhooks, so the webhook handler updates `DashboardState`. This is the existing mechanism and should be preserved.

### External Interfaces

| Interface | Protocol | Notes |
|-----------|----------|-------|
| `/video_feed` | HTTP MJPEG (multipart/x-mixed-replace) | Existing; already works |
| `/ws` | WebSocket JSON | Existing; 0.5s state push |
| `/trigger` | HTTP POST JSON | Existing; receives from detector webhook |
| `/api/process/start` | HTTP POST | New |
| `/api/process/stop` | HTTP POST | New |
| `/api/transcribe` | HTTP POST multipart | New; requires ffmpeg on PATH |
| `/api/sleep/prevent` | HTTP POST | New; requires wakepy |
| `/api/sleep/allow` | HTTP POST | New |
| `/api/videos/{filename}` | HTTP GET (range support) | New; serves video1-8.mp4 for `<video>` element |

---

## Build Order (Dependencies)

Building in this order minimizes blocked work and validates each layer before building on top of it.

```
Phase 1: Backend Extensions (no frontend needed to test)
  1a. api/process_manager.py    — test with curl /api/process/start
  1b. api/sleep_guard.py        — test with curl /api/sleep/prevent
  1c. api/transcribe.py         — test with curl -F audio=@test.webm /api/transcribe
  1d. /api/videos/{file}        — test video range request with browser
  1e. Extend /ws to include detector_running + workflow_phase fields

Phase 2: Frontend Foundation (no workflow logic yet)
  2a. Vite project scaffold (index.html, main.js, style.css)
  2b. MJPEG feed display (<img> src=/video_feed)
  2c. WebSocket connection + reconnect (ws.js)
  2d. Status panel (FPS, uptime, active tracks) bound to ws state
  2e. Keyboard shortcuts: start/stop/manual trigger

Phase 3: Video Overlay
  3a. CSS stacking layout (detection feed behind, video on top)
  3b. video.js: play/pause/hide controls
  3c. Marquee text overlay div
  3d. Manual trigger test (keyboard → play video2.mp4)

Phase 4: Audio Pipeline
  4a. audio.js: getUserMedia + MediaRecorder + FormData POST
  4b. Test /api/transcribe end-to-end with real mic
  4c. CNP/email pattern matching in backend (port from controller.py)

Phase 5: Kiosk Workflow (workflow.js)
  5a. State machine in JS: IDLE → GREETING → ASK_NAME → ...
  5b. Wire person_entered WebSocket event → workflow trigger
  5c. Wire video.onended → next workflow phase
  5d. Wire audio transcription result → next workflow phase
  5e. Timeout handling (patient walks away mid-flow)

Phase 6: Kiosk Hardening
  6a. Browser launch script (--kiosk flags)
  6b. FastAPI serves Vite dist/ as StaticFiles
  6c. Sleep prevention activation on system start
  6d. Romanian UI strings audit
  6e. Windows 11 Pro validation
```

---

## Anti-Patterns

### Anti-Pattern 1: Managing Video Playback via Python

**What people do:** Try to control `<video>` element playback from the FastAPI side by sending WebSocket commands to the browser.

**Why it's wrong:** Adds round-trip latency to every video transition. Video ended events must be acknowledged back to the server before the next transition can happen. State gets split between Python and JS, creating synchronization bugs.

**Do this instead:** The browser owns all video playback logic. Python only sends high-level events (`person_entered`). The JS workflow state machine decides which video to play and when.

### Anti-Pattern 2: Reassigning `img.src` to Toggle Feed Visibility

**What people do:** Set `img.src = ''` to hide the feed, then set it back to `/video_feed` to show it.

**Why it's wrong:** Reassigning src closes the MJPEG HTTP connection and restarts it. The browser re-issues the HTTP request, causing a blank frame gap and unnecessary network reconnection overhead.

**Do this instead:** Use CSS `opacity: 0` or `visibility: hidden`. The MJPEG connection stays open, the feed keeps running in the background, and switching back is instant.

### Anti-Pattern 3: Streaming Audio to Backend via WebSocket

**What people do:** Send MediaRecorder chunks in real-time over a WebSocket to avoid the 10-second wait.

**Why it's wrong:** For this use case, the recording always finishes before transcription starts. Streaming chunks adds complexity (chunk reassembly, WebSocket flow control, error handling mid-stream) with no user-facing benefit. Whisper is not designed for streaming — it processes the full audio at once.

**Do this instead:** Record locally, post the complete blob. One HTTP call, clear success/failure semantics.

### Anti-Pattern 4: Running Detector in the Same FastAPI Process

**What people do:** Import and call the detector's main loop from within the FastAPI app so there is only one process.

**Why it's wrong:** The detector loop is CPU-bound (YOLO inference at 15 FPS). Running it in the same Python process blocks the asyncio event loop, degrading WebSocket/HTTP response times. The `DashboardServer` already uses a separate thread, but FastAPI's async endpoints share the thread pool.

**Do this instead:** The detector runs as a subprocess (`subprocess.Popen`). The trigger webhook is already the communication bridge. This is the existing architecture — preserve it.

### Anti-Pattern 5: Multiple Separate Servers (Flask + FastAPI + Vite)

**What people do:** Keep Flask on port 5050 for the webhook, FastAPI on port 8080 for the dashboard, and Vite dev server on port 5173.

**Why it's wrong:** The browser makes requests to all three origins, requiring CORS configuration. The operator must start three processes. The kiosk browser cannot use `localhost:5173` in production.

**Do this instead:** Merge everything into FastAPI (port 8080). The trigger endpoint moves from Flask to FastAPI. In production, FastAPI serves the Vite build as StaticFiles. In development, Vite proxies API calls to FastAPI (`vite.config.js: server.proxy`).

---

## Scaling Considerations

This is a single-kiosk local system. Scaling considerations are minimal and practical:

| Scale | Architecture Adjustment |
|-------|------------------------|
| 1 kiosk (now) | Single FastAPI process + detector subprocess. No changes. |
| 2-5 kiosks (same clinic) | Each kiosk is an independent instance. No shared state needed. |
| Remote monitoring | Add a log endpoint that POSTs structured events to a central server. Existing webhook infrastructure supports this. |
| Multiple clinics | Parameterize WEBHOOK_URL and CAMERA_ID per deployment. Docker image per clinic. No code changes. |

**First bottleneck:** Whisper transcription time (~1-3s on modern x86 hardware with int8). At 1 patient at a time (which is the physical reality of a single entrance), this is not a bottleneck.

**No bottleneck that requires architectural changes at any realistic scale for this use case.**

---

## Sources

- MJPEG streaming in FastAPI: [existing `dashboard/web.py`] — already working
- FastAPI StaticFiles: https://fastapi.tiangolo.com/tutorial/static-files/ (MEDIUM confidence)
- FastAPI subprocess: https://github.com/fastapi/fastapi/discussions/7442 (MEDIUM confidence)
- Web Audio API / MediaRecorder: https://codesignal.com/learn/courses/real-time-audio-transcription-with-web-audio-api-1/ (MEDIUM confidence)
- Whisper streaming with WebSocket: https://github.com/ScienceIO/whisper_streaming_web (reference, not used)
- Chrome kiosk flags: https://smartupworld.com/chromium-kiosk-mode/ (HIGH confidence — documented by Google)
- wakepy cross-platform sleep prevention: https://wakepy.readthedocs.io/stable/ (HIGH confidence — official docs)
- HTML5 video z-index overlay: https://teamtreehouse.com/community/how-do-i-make-a-div-visible-on-top-of-an-html5-fullscreen-video (MEDIUM confidence)
- Vite proxy for development: https://vite.dev/config/ (HIGH confidence — official docs)

---

*Architecture research for: Vite frontend + FastAPI backend kiosk web platform*
*Researched: 2026-03-05*
*Supersedes: 2026-03-04 ARCHITECTURE.md (python-mpv approach)*
