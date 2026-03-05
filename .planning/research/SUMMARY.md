# Project Research Summary

**Project:** Clinic Entrance Kiosk — Web Platform (Milestone 2)
**Domain:** Kiosk web app — real-time detection dashboard + patient video check-in + offline Romanian STT
**Researched:** 2026-03-05
**Confidence:** HIGH

## Executive Summary

This project replaces a fragile two-process kiosk setup (VLC RC socket + Flask controller) with a single unified browser window running on top of an extended FastAPI backend. The existing Python detection pipeline (VideoStream → PersonTracker → EntryAnalyzer → WebhookSender) is proven and remains untouched; what changes is everything the patient and operator see. The correct approach is a Vite + vanilla TypeScript frontend with zero UI framework overhead — this is a five-screen state machine, not a CRUD app, and React/Vue would add 40-80KB of runtime for zero benefit. All media APIs (MJPEG display, HTML5 video playback, microphone capture, screen wake lock) are browser-native and require no npm dependencies beyond the Vite build tool itself.

The recommended architecture is a clean browser/Python split: the browser owns all presentation logic (which video plays, when to record, UI transitions), Python owns all inference and OS integration (YOLO detection, Whisper transcription, subprocess management, sleep prevention). Communication flows through three channels: an MJPEG stream for the live detection feed, a WebSocket for state pushes at 0.5-second intervals, and REST endpoints for commands (start/stop detector, POST audio blob, prevent sleep). FastAPI serves the Vite production build as StaticFiles, eliminating the need for any separate server in production.

The critical risks center on browser API behavior in a 24/7 kiosk context. MJPEG display via a plain `<img>` tag causes a documented memory leak that will crash the tab after 2-4 hours — a fetch-to-canvas pattern with explicit URL revocation is mandatory from day one. Chrome's autoplay policy will silently block instructional video playback without the `--autoplay-policy=no-user-gesture-required` kiosk flag, and the AudioContext starts in `suspended` state and must be resumed inside a user gesture handler. On Windows (the production target), `subprocess.terminate()` leaves camera-holding orphan processes — psutil tree kill is required for reliable start/stop cycling.

---

## Key Findings

### Recommended Stack

The frontend requires only Vite 7.x with the `vanilla-ts` template. No additional npm packages are needed — all required APIs (WebSocket, MJPEG via fetch, HTML5 video, MediaRecorder, Screen Wake Lock) are browser-native. Node.js 20.19+ or 22.12+ is required for Vite 7 (verify on clinic mini PC before starting). The backend adds two new Python packages: `wakepy 1.0.0` for cross-platform OS-level sleep prevention (no admin rights required) and `aiofiles` as an implicit FastAPI StaticFiles dependency. Everything else — FastAPI, python-multipart, faster-whisper 1.2.1 — is already installed.

**Core technologies:**
- Vite 7.x + vanilla TypeScript: Build tool and kiosk UI — zero runtime overhead for a single-screen state machine app
- HTML5 native APIs (WebSocket, MediaRecorder, Screen Wake Lock, fetch): All media and communication — no npm libraries required
- FastAPI (existing, extended): Process management, transcription, sleep prevention endpoints; serves Vite dist/ as StaticFiles
- faster-whisper 1.2.1 (existing): Romanian offline STT — accepts WebM/Opus via ffmpeg, `vad_filter=True` already enabled in codebase
- wakepy 1.0.0 (new): Cross-platform sleep prevention — wraps `caffeinate` (macOS) and `SetThreadExecutionState` (Windows), no admin rights
- Chrome `--kiosk` flag: Production browser launcher — already installed on clinic PC, 150-200MB lighter than Electron

**Critical version/compatibility notes:**
- Vite 7 requires Node.js 20.19+ or 22.12+ — check clinic mini PC before starting Phase 2
- MediaRecorder must use `audio/webm;codecs=opus` — always call `MediaRecorder.isTypeSupported()` before instantiation
- Screen Wake Lock requires secure context — `localhost` qualifies; never serve via machine hostname over plain HTTP
- `keypress` event is deprecated and removed in Chrome 142+ — use `keydown` with `event.code`

### Expected Features

**Must have (P1 — table stakes, required to replace current system):**
- Idle video loop (VIDEO1) — blank screen signals "broken" to arriving patients
- MJPEG detection feed display — operator proof the system is working
- WebSocket entry event reception and workflow trigger — the core integration point
- Sequential instructional video playback (VIDEO2-8) — replaces all VLC RC commands
- Browser microphone recording to `/api/transcribe` — replaces sounddevice, same 10-second fixed duration
- On-screen STT text feedback (Ascultare / Procesare / result) — replaces VLC marquee
- System start/stop via UI button and keyboard shortcuts (F1=start/stop, F2=manual trigger, Escape=stop) — no more terminal commands
- System status display (FPS, uptime, active tracks) — operator health at a glance
- Screen Wake Lock with OS-level fallback via wakepy — 24/7 kiosk cannot sleep
- Fullscreen/kiosk mode via `document.documentElement.requestFullscreen()` on the container element
- WebSocket exponential backoff auto-reconnect — prerequisite for all event-driven features
- All text in Romanian, hardcoded — no i18n library overhead

**Should have (P2 — add after first clinic day validation):**
- Multi-attempt STT with re-prompt (MAX_RETRIES=2, then operator intervention)
- VAD silence detection — stop recording when patient stops speaking instead of fixed 10 seconds
- Confirmation overlay — show captured name/CNP/email, patient confirms before data submission
- Snapshot thumbnails in entry log — visual audit trail from existing webhook base64 field
- Process restart button in operator panel — avoid requiring SSH for non-technical clinic staff
- Manual trigger button — operator testing without walking in front of camera

**Defer to v2+ (not essential for launch):**
- Touchscreen fallback (hygiene concern in medical setting, defeats speech-first design)
- EHR webhook integration (no specific target system identified yet)
- Multi-language support (only if patient demographics require it)
- Queue number display (only if clinic adds queue management)

### Architecture Approach

The system separates into two cleanly bounded layers. The browser is the entire presentation layer: it owns video playback sequencing, microphone recording timing, UI state transitions, and all DOM updates. Python is the control and inference layer: it owns person detection, Whisper transcription, OS subprocess management, and sleep prevention. The two layers communicate through well-defined channels — Python never controls video playback timing or DOM state, and JavaScript never performs audio inference or process management directly. The detector always runs as a subprocess (not in-process) because YOLO inference is CPU-bound and would block FastAPI's asyncio event loop.

**Major components:**
1. **App State + Workflow JS** (`state.js`, `workflow.js`) — single source of truth for kiosk phase (IDLE → TRIGGERED → GREETING → ASK_NAME → RECORDING → CONFIRM → IDLE); drives all DOM updates via `ui.js`
2. **WebSocket Handler** (`ws.js`) — subscribes to `/ws`, exponential backoff reconnect (1s base, 30s max, 2x multiplier), dispatches events to App State
3. **Video Overlay** (`video.js`) — CSS z-index stacked `<video>` over MJPEG feed; opacity transitions; Fullscreen API called on container div, never on the video element itself
4. **Audio Pipeline** (`audio.js`) — MediaRecorder with stop-and-collect (full blob, not chunks) converted to 16kHz mono WAV before POST to `/api/transcribe`
5. **Process Manager** (`api/process_manager.py`) — `subprocess.Popen` for `main.py`; psutil tree kill on Windows for reliable teardown; `detector_running()` state surfaced to WebSocket
6. **WhisperEngine** (`api/transcribe.py`) — loaded once at FastAPI startup; ffmpeg converts WebM to 16kHz mono WAV; transcribes with `vad_filter=True, language='ro'`
7. **SleepGuard** (`api/sleep_guard.py`) — wakepy `keep.presenting()` context manager; activated on system start, deactivated on stop

**Key project structure additions:**
```
clinic-entrance-detector/
├── api/
│   ├── process_manager.py   # subprocess.Popen + psutil tree kill
│   ├── transcribe.py        # /api/transcribe, ffmpeg + faster-whisper
│   └── sleep_guard.py       # /api/sleep/prevent|allow, wakepy
└── frontend/
    └── src/
        ├── main.ts          # entry point, wires modules
        ├── state.ts         # single source of truth
        ├── ws.ts            # WebSocket + exponential backoff reconnect
        ├── workflow.ts      # kiosk state machine
        ├── video.ts         # HTML5 video overlay control
        ├── audio.ts         # MediaRecorder + WAV conversion + POST
        ├── shortcuts.ts     # keyboard shortcut bindings
        └── ui.ts            # DOM updates (no logic)
```

### Critical Pitfalls

1. **MJPEG `<img>` tag memory leak** — use fetch-to-canvas with `URL.revokeObjectURL()` after each frame draw. The `<img>` tag pattern will exhaust browser memory after 2-4 hours at 15 FPS/720p. Non-negotiable for 24/7 kiosk. Build this correctly in Phase 2 — retrofitting is disruptive to all other frontend work.

2. **AudioContext starts suspended** — create lazily inside the "Start System" button click handler (first user gesture); always check `audioCtx.state === 'running'` before starting any recording. Silent failure produces empty transcriptions with no visible error.

3. **Python subprocess zombie processes on Windows** — `process.terminate()` kills only the root process on Windows, leaving OpenCV/BoT-SORT child processes holding the camera device. The next "Start" click fails with "camera already in use." Use psutil tree kill. Test 5 consecutive start/stop cycles on Windows 11 before declaring this feature complete.

4. **HTML5 video autoplay silently blocked** — always `await video.play()` with a catch handler; add `--autoplay-policy=no-user-gesture-required` to the Chrome kiosk launch script. Cold-boot test: launch Chrome with `--kiosk` with no prior user interaction and verify video plays.

5. **Screen Wake Lock released on tab visibility change** — the browser spec mandates release when `visibilityState` becomes `'hidden'`. Add a `visibilitychange` listener that re-requests the lock. Pair with OS-level prevention via wakepy (the real defense for 24/7); browser Wake Lock alone is insufficient.

6. **MediaRecorder WebM chunk format incompatible with Whisper** — only the first MediaRecorder chunk contains a valid WebM container header; individual chunks are not standalone decodable files. Use stop-and-collect (one complete blob per recording) or convert to 16kHz mono WAV in the browser before posting. WAV is Whisper's native format and eliminates backend ffmpeg conversion latency.

7. **Vite dev proxy silently drops WebSocket upgrades** — add `ws: true` to every `/ws/*` proxy entry in `vite.config.ts`. Without it, WebSocket connections fail during development, blocking all integration testing from the start.

---

## Implications for Roadmap

Based on the build-order dependency graph in `ARCHITECTURE.md` and pitfall-to-phase mapping in `PITFALLS.md`, the following 6-phase structure is strongly recommended. Each phase is independently testable before the next begins.

### Phase 1: Backend Extensions

**Rationale:** The entire frontend depends on stable backend endpoints. Building these first means every frontend feature can be validated with curl before any JavaScript is written. No blocked work downstream, and process management bugs (especially Windows camera lock) are caught before the frontend adds another layer of complexity.

**Delivers:** Four new FastAPI endpoint groups (`/api/process/start|stop|status`, `/api/transcribe`, `/api/sleep/prevent|allow`, `/api/videos/{filename}`), extended WebSocket state payload (`detector_running`, `workflow_phase`), video file serving.

**Addresses:** System start/stop, transcription pipeline, sleep prevention, video serving (all P1 table stakes)

**Critical pitfall to avoid:** Implement psutil tree kill in `process_manager.py` from the start — test 5x start/stop cycles on Windows 11 before moving forward. Do not use `process.terminate()` alone.

**Research flag:** Standard patterns — FastAPI routing and subprocess management are well-documented. No additional research phase needed.

### Phase 2: Frontend Foundation

**Rationale:** Establish the Vite scaffold, MJPEG feed (correctly via fetch-to-canvas), WebSocket connection with reconnect, and status display before any workflow logic is added. Validates the dev environment (critically including Vite proxy `ws: true`) before complexity is layered on.

**Delivers:** Vite project scaffolded with `vanilla-ts` template; MJPEG feed rendering via fetch-to-canvas with URL revocation; WebSocket connected with exponential backoff reconnect; system status panel showing live FPS/uptime/active tracks; keyboard shortcuts wired (F1/F2/Escape); `navigator.mediaDevices` availability guard.

**Addresses:** MJPEG feed display, system status, WebSocket auto-reconnect, keyboard shortcuts (all P1)

**Critical pitfalls to avoid:** Implement fetch-to-canvas from day one — not `<img>` tag. Add `ws: true` to Vite proxy on first configuration. Add `navigator.mediaDevices` guard in initialization so mic unavailability surfaces immediately.

**Research flag:** Standard patterns for Vite scaffold and WebSocket client. The MJPEG multipart boundary parser is non-trivial — refer to PITFALLS.md Pitfall 1 code sketch.

### Phase 3: Video Overlay

**Rationale:** Video playback is the core patient-facing behavior and must be solid and independently tested before the audio pipeline is layered on top. Isolating concerns means video transition bugs are clearly separate from audio/transcription bugs.

**Delivers:** CSS z-index stacking layout (MJPEG feed behind, video on top, text overlay on top of video); idle loop (VIDEO1 with `loop` attribute); play/pause/hide controls in `video.ts`; marquee text overlay `<div>`; manual trigger test (F2 → video2.mp4 plays and transitions correctly).

**Addresses:** Idle video loop, sequential video playback, on-screen text feedback (all P1)

**Critical pitfalls to avoid:** Fullscreen API must be called on the container div, never on the `<video>` element directly. Never reassign `img.src` to hide the MJPEG feed — use CSS `opacity: 0` (reassigning src terminates the MJPEG connection). Always `await video.play()` with catch. Add `--autoplay-policy=no-user-gesture-required` to Chrome launch script in this phase.

**Research flag:** Standard HTML5 video patterns with CSS stacking. Exact patterns documented in ARCHITECTURE.md Pattern 2. No additional research needed.

### Phase 4: Audio Pipeline

**Rationale:** Audio capture depends on Phase 3 (recording happens after a video prompt ends). The audio format contract must be defined before workflow integration so both the browser and backend agree. Getting the MediaRecorder → WAV → Whisper pipeline working end-to-end in isolation saves significant debugging time in Phase 5.

**Delivers:** `audio.ts` with getUserMedia + MediaRecorder + stop-and-collect; PCM-to-WAV conversion before POST; working end-to-end `/api/transcribe` with real microphone input; CNP/email pattern matching ported from `controller.py` to backend.

**Addresses:** Browser microphone recording and transcription (P1)

**Critical pitfalls to avoid:** Create AudioContext lazily inside the "Start System" click handler. Always check `audioCtx.state === 'running'` before recording. Use stop-and-collect (not chunked streaming). Convert to 16kHz mono WAV before POST — not raw WebM blob. Only call `getUserMedia` from `localhost`.

**Research flag:** The in-browser PCM-to-WAV conversion (float32 samples to 16-bit WAV header) is non-trivial. A working code reference should be confirmed before implementation. ARCHITECTURE.md Pattern 3 and PITFALLS.md Pitfall 8 have the relevant patterns.

### Phase 5: Kiosk Workflow State Machine

**Rationale:** The workflow (`workflow.ts`) wires all previous phases together into the complete patient interaction sequence. It requires video, audio, and WebSocket all working correctly — placing it last among core phases ensures bugs surface in their true origin rather than being masked by state machine complexity.

**Delivers:** JS state machine (IDLE → TRIGGERED → GREETING → ASK_NAME → RECORDING_NAME → CONFIRM → IDLE); `person_entered` WebSocket event triggering workflow; `video.onended` advancing to next phase; transcript result advancing to next phase; 30-second timeout handling for patient abandonment; Romanian UI strings audit.

**Addresses:** Full patient workflow — replaces all behavior currently in `controller.py`; WebSocket entry event reception; fullscreen mode (P1)

**Critical pitfalls to avoid:** Implement 30-second countdown timer per recording phase (patient abandonment — system must return to idle, not wait forever). Show "Ascultare..." pulsing indicator while recording is active. Suppress entry beep/notification during active video playback. Never log CNP or email to browser console — mask as `CNP: ****1234`.

**Research flag:** The existing `controller.py` is the authoritative specification for workflow behavior. No external research needed — port the state logic, don't redesign it.

### Phase 6: Kiosk Hardening

**Rationale:** Production readiness (kiosk flags, security, Windows validation) is addressed last, after core workflow is proven working. These are non-functional concerns that depend on having something functional to harden.

**Delivers:** Chrome kiosk launch script with all required flags (`--kiosk`, `--autoplay-policy=no-user-gesture-required`, `--disable-session-crashed-bubble`, `--noerrdialogs`, `--disable-infobars`, `--user-data-dir`); FastAPI serving Vite `dist/` as StaticFiles; two-layer sleep prevention (Screen Wake Lock + wakepy) activated on system start; JavaScript keyboard escape interceptors (F12, Ctrl+J, Shift+Esc); `visibilitychange` listener for wake lock re-acquisition; entry log capped at 100 rows; Windows 11 Pro full workflow validation.

**Addresses:** Kiosk mode production deployment, sleep prevention hardening, kiosk security, entry log DOM performance

**Critical pitfalls to avoid:** Both sleep prevention layers (browser Wake Lock + wakepy backend) must be active simultaneously — browser-only is insufficient for 24/7. Add `visibilitychange` listener for wake lock re-acquisition. Perform the entire workflow on Windows 11 Pro before declaring done — path separators, signal handling, audio device names, and mic permission flow all differ from macOS development environment.

**Research flag:** Windows 11 Assigned Access kiosk mode (Settings → Accounts → Assigned Access) may be the correct production mechanism for OS-level keyboard lockdown, and its interaction with Chrome `--kiosk` and wakepy should be validated on the target hardware. Brief investigation during this phase.

### Phase Ordering Rationale

- Backend first (Phase 1) ensures every subsequent feature can be independently tested with curl; catches Windows-specific subprocess bugs early
- Frontend foundation before workflow (Phases 2-4 before Phase 5) isolates rendering, video, and audio bugs so they are not tangled with state machine logic
- Audio pipeline (Phase 4) after video (Phase 3) because recording always follows a video prompt — the dependency is real
- Workflow state machine (Phase 5) last among core features because it integrates all prior phases — bugs in Phase 5 that originate in Phases 2-4 are far easier to diagnose when those phases were independently validated
- Hardening (Phase 6) at the end because kiosk-mode deployment behavior cannot be fully verified until the complete workflow is working

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Audio Pipeline):** The in-browser PCM-to-WAV conversion needs a concrete, verified code implementation reference before work starts. The pattern is documented in research but needs a working example confirmed against Chrome's AudioContext output format.
- **Phase 6 (Kiosk Hardening):** Windows 11 Assigned Access kiosk mode interaction with Chrome `--kiosk` flag and wakepy needs a quick validation pass on the actual target hardware during this phase.

Phases with well-documented standard patterns (skip additional research):
- **Phase 1 (Backend Extensions):** FastAPI routing, subprocess.Popen, and faster-whisper integration are well-documented; the existing codebase already has patterns to follow.
- **Phase 2 (Frontend Foundation):** Vite scaffold, WebSocket client with exponential backoff, CSS layout are all standard — ARCHITECTURE.md has the exact implementation patterns.
- **Phase 3 (Video Overlay):** HTML5 video with CSS z-index stacking is thoroughly documented in ARCHITECTURE.md Pattern 2.
- **Phase 5 (Workflow State Machine):** The existing `controller.py` is the authoritative specification. Port, don't redesign.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified against official docs (Vite 7 npm, MDN APIs, wakepy readthedocs, faster-whisper PyPI). Version compatibility confirmed. |
| Features | HIGH | Requirements derived from existing codebase (`controller.py`, `dashboard/web.py`) and `PROJECT.md` — not speculative. Ground truth is the existing code. |
| Architecture | HIGH | Patterns verified from multiple authoritative sources. Build order derived from actual dependency analysis. Supersedes prior python-mpv architecture (2026-03-04). |
| Pitfalls | HIGH | All 10 critical pitfalls traced to official bug trackers, MDN docs, or Chrome developer documentation. Not community hearsay. |

**Overall confidence:** HIGH

### Gaps to Address

- **Whisper model latency on clinic mini PC:** faster-whisper `medium` + int8 may take 30-60 seconds on underpowered hardware. Benchmark on the actual Windows 11 mini PC during Phase 4 — downgrade to `small` model if latency is unacceptable. The UI must show a loading state during transcription regardless.
- **Camera mic permission in Chrome kiosk:** `getUserMedia` in `--kiosk` mode may require `--use-fake-ui-for-media-stream` during development or requires explicit operator interaction on first kiosk profile boot. Verify this flow before Phase 4 is declared done.
- **ffmpeg availability on Windows 11 mini PC:** The `/api/transcribe` endpoint requires `ffmpeg` on PATH for WebM-to-WAV conversion. Verify or add ffmpeg installation to the deployment checklist before Phase 1 testing.
- **Node.js version on clinic mini PC:** Vite 7 requires Node.js 20.19+ or 22.12+. Check before starting Phase 2 frontend scaffold.

---

## Sources

### Primary (HIGH confidence)
- Vite official docs — https://vite.dev/guide/ — version 7.3.1, Node.js requirements, proxy configuration with `ws: true`
- MDN Screen Wake Lock API — https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API — auto-release on visibility change, secure context requirement
- MDN MediaStream Recording API — https://developer.mozilla.org/en-US/docs/Web/API/MediaStream_Recording_API/Using_the_MediaStream_Recording_API — MediaRecorder stop-and-collect pattern
- MDN getUserMedia — https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia — secure context (localhost) requirement
- wakepy readthedocs 1.0.0 — https://wakepy.readthedocs.io/stable/ — `keep.presenting` mode, Windows/macOS behavior, no admin rights
- faster-whisper PyPI — https://pypi.org/project/faster-whisper/ — v1.2.1, `vad_filter` parameter
- FastAPI StaticFiles — https://fastapi.tiangolo.com/tutorial/static-files/ — StaticFiles mount pattern
- Chrome autoplay policy — https://developer.chrome.com/blog/autoplay — `NotAllowedError`, `--autoplay-policy` flag
- Chrome Wake Lock — https://developer.chrome.com/docs/capabilities/web-apis/wake-lock — visibility change auto-release behavior
- Existing codebase: `dashboard/web.py`, `controller.py`, `.planning/PROJECT.md` — primary specification source

### Secondary (MEDIUM confidence)
- Chromium kiosk flags — https://smartupworld.com/chromium-kiosk-mode/ — `--kiosk`, `--noerrdialogs`, `--autoplay-policy`, `--disable-infobars` flags
- psutil readthedocs — https://psutil.readthedocs.io/en/latest/ — process tree kill pattern on Windows
- FastAPI subprocess discussion — https://github.com/fastapi/fastapi/discussions/7442 — subprocess management patterns
- Vite proxy `ws: true` — https://vite.dev/config/server-options — WebSocket proxy configuration requirement
- Chrome Wake Lock guide — https://web.dev/blog/screen-wake-lock-supported-in-all-browsers — cross-browser support confirmation

### Tertiary (LOW confidence)
- Firefox MJPEG memory leak bug — https://bugzilla.mozilla.org/show_bug.cgi?id=662195 — confirms memory leak risk (Firefox-specific but Chromium also degrades over time)
- MediaRecorder chunk format issue — https://github.com/chrisguttandin/extendable-media-recorder/issues/638 — WebM chunk header incompatibility detail
- WebSocket power-saving disconnect — https://www.pixelstech.net/article/1719122489-the-pitfall-of-websocket-disconnections-caused-by-browser-power-saving-mechanisms — background tab throttling behavior

---

*Research completed: 2026-03-05*
*Supersedes: 2026-03-04 SUMMARY.md (python-mpv / VLC migration focus)*
*Ready for roadmap: yes*
