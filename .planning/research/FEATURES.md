# Feature Research

**Domain:** Clinic kiosk web platform — real-time entrance detection dashboard + patient video check-in + STT data capture
**Researched:** 2026-03-05
**Confidence:** HIGH (project requirements are well-defined; this is implementation scoping, not market discovery)

---

## Context

This is a subsequent-milestone research task. The backend systems are proven and working. The
question is: given we must build a unified Vite frontend that merges the detection dashboard
(FastAPI/WebSocket/MJPEG) and the VLC controller (video playback + STT), which features are
load-bearing vs. differentiating vs. should-never-be-built?

There are two user roles with distinct UX modes:

- **Patient**: sees fullscreen instructional videos, hears questions, speaks answers — passive
- **Operator**: monitors detection state, manages system, intervenes if needed — active

Both roles run in the same browser window, switching modes on detection events.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the operator or patient assumes exist. Missing any of these = system feels broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Live MJPEG video feed with detection overlays | Operator must see what the camera sees. Bounding boxes and zones are the proof the system is working. | LOW | Already served by FastAPI `/video_feed`. Frontend just needs an `<img>` tag pointed at it — no canvas required unless overlays need to be added client-side. |
| System status indicators (FPS, active tracks, uptime, camera connected) | Standard for any always-on monitoring system. Operator needs to know at a glance if the system is healthy. | LOW | `DashboardState` already pushes all metrics via WebSocket `/ws`. Front-end just renders them. |
| Entry event log with timestamp, person ID, confidence | Operator needs audit trail. Without a log, incidents are unverifiable. | LOW | Already stored in `event_log` deque (up to 100 events) in `DashboardState`. Needs a table UI. |
| One-click system start/stop | If the operator cannot start or stop the detector without a terminal, the system is unusable in production. | MEDIUM | Requires new FastAPI endpoints (`/api/process/start`, `/api/process/stop`) that manage the detector subprocess. The frontend button calls these. |
| Instructional video playback triggered by entrance event | Core product behavior — the whole point of the controller replacement. Patient watches video in same window. | MEDIUM | HTML5 `<video>` element replacing VLC. Backend fires webhook → frontend receives via WebSocket → video plays. |
| Seamless idle video loop (VIDEO1) | Standard kiosk behavior. Blank screen while waiting signals "broken." | LOW | HTML5 `<video loop>` with `playsinline`. No black frames between loops unlike VLC. |
| On-screen text feedback during STT (Ascultare... / Procesare... / result) | Patient must know the system is listening and has understood them. Without this, they repeat themselves or leave. | LOW | Replaces VLC marquee. CSS overlay on `<video>` element. |
| Browser microphone recording and sending audio to backend | STT chain requires browser mic → backend transcription. Without this, name/CNP/email capture breaks. | MEDIUM | `MediaRecorder` API. Must request permissions proactively on page load. 10-second fixed-duration recording matching current `controller.py` behavior. |
| Screen/sleep prevention while system is active | If the screen turns off, a patient arriving sees a dark screen and leaves. | LOW | Screen Wake Lock API (`navigator.wakeLock.request('screen')`) is now supported in all major browsers as of 2025 — no OS calls needed. Fallback: call `/api/system/wake` to trigger `caffeinate` / `powercfg` on backend. |
| Fullscreen / kiosk mode for production | Window chrome (URL bar, tabs) must be invisible on the reception desk. | LOW | Chrome `--kiosk` flag on production. Frontend calls `document.documentElement.requestFullscreen()` when operator starts the system. |
| Keyboard shortcuts: Start/Stop, manual trigger, emergency stop, toggle view | Operator uses keyboard, not mouse. Without shortcuts the production workflow is awkward. | LOW | Vanilla `keydown` event listeners. No library needed. Define: F1=start/stop, F2=manual trigger, Escape=emergency stop, F3=toggle detection/kiosk view. |
| All UI text in Romanian | The clinic staff and patients are Romanian-speaking. English text breaks trust. | LOW | Hardcode strings — no i18n library overhead needed. |
| WebSocket reconnect on disconnect | The FastAPI WebSocket will disconnect if the detector restarts. Without auto-reconnect, the dashboard goes stale silently. | LOW | Exponential back-off reconnect loop. Standard pattern. |

### Differentiators (Competitive Advantage)

Features that separate this from a standard FastAPI dashboard or commercial kiosk solution.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Unified single-window experience (detection + kiosk in one) | Eliminates the two-process, two-window fragility of the current VLC + Flask setup. One window to rule them all. | MEDIUM | The `<video>` element overlays the feed as a modal/fullscreen layer when triggered, then returns. State machine controls transitions. |
| HTML5 video replaces VLC entirely | VLC RC socket interface is unreliable (race conditions, timing hacks with `time.sleep()`). HTML5 video is synchronous event-driven: `video.onended`, `video.play()`. | LOW | Remove the 2-second VLC startup delay, the RC socket connection, and all `time.sleep()` duration hacks. |
| Event-driven workflow state machine in browser | The frontend tracks current workflow state (IDLE → TRIGGERED → VIDEO2 → RECORDING_NAME → ...) which enables retry UI, progress indicators, and timeout handling without polling. | MEDIUM | JS `EventTarget`-based state machine or simple switch on state enum. Backend pushes state changes via WebSocket. |
| VAD-based silence detection for mic recording | Current approach records fixed 10 seconds regardless of whether the patient has finished speaking. VAD stops recording when speech ends, making the interaction feel responsive. | MEDIUM | Silero VAD is built into `faster_whisper` (`vad_filter=True` — already enabled). Frontend can use WebRTC VAD or just send audio after silence threshold using `AudioWorkletNode` amplitude analysis. |
| Multi-attempt STT with re-prompt | If the CNP or email transcription fails validation, re-prompt and re-record without restarting the whole workflow. Critical for production reliability with elderly patients. | MEDIUM | State machine has retry counts per capture step. MAX_RETRIES=2 then fallback to operator intervention. |
| Snapshot thumbnail in entry log | Entry events have a `snapshot` base64 field in the webhook payload. Displaying it in the log gives the operator visual confirmation of who entered. | LOW | Already in the webhook payload. Render as a 48px thumbnail `<img>` in the event log table. |
| Manual trigger button for testing | Operators need to test the workflow without walking in front of the camera. | LOW | Calls existing `/api/test-webhook` endpoint (already implemented in `dashboard/web.py`). |
| Process health indicator with restart button | Knowing the detector process is running (not just the dashboard) and being able to restart it without SSH is critical for non-technical clinic staff. | MEDIUM | `/api/process/status` endpoint + colored dot indicator + restart button in operator panel. |
| Confirmation overlay before data submission | Show captured name/CNP/email on screen, give patient 5 seconds to confirm or re-record. Prevents submitting garbled data. | MEDIUM | Text overlay layer over idle video. Wait for `Da`/confirmation or timeout. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| React/Vue/Svelte framework | Seems like standard practice; rich component ecosystem | Adds build complexity, bundle size, and a dependency tree that conflicts with the "extremely lightweight" constraint in PROJECT.md. The UI is a state machine with ~5 screens — not a CRUD app that needs reactivity at scale. | Vanilla JS with Vite. 3 files: `main.js`, `style.css`, `index.html`. Zero framework overhead. |
| Canvas-based overlay for detection boxes | Seems like it enables richer overlay UX | MJPEG frames are already annotated server-side by OpenCV in `main.py`. Redrawing them on a canvas doubles CPU work, requires frame-sync logic, and has documented performance issues in browsers with HD MJPEG. | Use the existing server-rendered MJPEG stream directly with an `<img>` tag. If additional overlays are needed, add them as CSS-positioned `<div>` elements updated from WebSocket data. |
| Web Speech API (browser-native STT) | Built-in, no backend needed | Chrome-only in kiosk mode, requires internet for Google's STT backend, cannot be tuned for Romanian dialect, and loses the `initial_prompt` feature that makes CNP/email extraction work. | Keep Faster Whisper offline on the backend. Browser records raw audio and sends to `/api/transcribe`. |
| Touchscreen UI | Intuitive for many users | Adds a hygiene concern for a medical reception kiosk, requires a full touch-optimized component library, and defeats the speech-first differentiator. The operator uses keyboard shortcuts, not touch. | Speech-first with keyboard shortcut fallback for operator. Touch is explicitly out of scope per PROJECT.md. |
| User authentication / login screen | "Should be secure" | The system is on a local network, single operator, runs in a kiosk. An auth screen adds friction with zero security benefit (the machine is physically locked to the reception desk). | No auth. Document that network isolation is the security boundary. |
| i18n / translation system | "What if we add English later?" | Adds library overhead and indirection for a system that is explicitly Romanian-only with hardcoded strings per PROJECT.md constraints. | Hardcode Romanian strings. If a second language is ever needed, add it then — don't architect for it now. |
| Persistent patient data storage in frontend | "Show patient history" | The frontend is a kiosk — it must not retain PII between sessions. Storing patient data in `localStorage` or IndexedDB is a GDPR liability on a shared terminal. | All captured data goes immediately to the backend webhook. Frontend clears all state on workflow completion and on page load. |
| WebRTC video streaming | "More modern than MJPEG" | WebRTC requires a signaling server, STUN/TURN infrastructure, and ICE negotiation. This is a local network, single-camera system where MJPEG already works at 15 FPS with zero configuration. | Keep MJPEG. It is exactly the right tool for a single-client, LAN-only, low-latency feed. |
| Real-time video encoding / transcoding | "Better quality" | The detection pipeline already produces 1280x720 JPEG frames at 15 FPS. Re-encoding in the browser wastes CPU that the detector needs. | Accept the MJPEG stream as-is. Quality is already configured via `IMWRITE_JPEG_QUALITY=80`. |

---

## Feature Dependencies

```
[Screen Wake Lock]
    └──requires──> [System Active State] (only lock while system is running)

[Instructional Video Playback]
    └──requires──> [WebSocket Entry Event] (trigger from detector)
    └──requires──> [Idle Video Loop] (must stop loop before playing workflow video)

[STT Recording]
    └──requires──> [Microphone Permission] (must be granted before workflow starts)
    └──requires──> [Video Playback] (record after video ends, not during)

[STT Recording] ──sends-to──> [Backend /api/transcribe]
    └──returns──> [On-Screen Text Feedback]
    └──returns──> [Workflow State Advance]

[Multi-attempt STT]
    └──requires──> [Workflow State Machine] (needs retry count tracking)
    └──requires──> [STT Recording]

[Confirmation Overlay]
    └──requires──> [All Capture Steps Complete] (name + CNP + email)
    └──requires──> [On-Screen Text Feedback]

[Process Start/Stop]
    └──requires──> [Backend Process Management API] (/api/process/start, /api/process/stop)

[System Status Display]
    └──requires──> [WebSocket Connection] (/ws live state feed)

[Manual Trigger]
    └──requires──> [/api/test-webhook endpoint] (already exists in dashboard/web.py)

[Keyboard Shortcuts]
    └──enhances──> [Process Start/Stop] (F1 binding)
    └──enhances──> [Manual Trigger] (F2 binding)
    └──enhances──> [Emergency Stop] (Escape binding)

[Entry Log with Snapshots]
    └──requires──> [WebSocket event_log feed] (already in DashboardState)
```

### Dependency Notes

- **Microphone permission requires early request**: `getUserMedia()` must be called on user gesture before the first recording step. Best triggered by the "Start System" button click — the operator gesture that starts the workflow.
- **WebSocket reconnect gates everything**: If the WebSocket is disconnected, the frontend cannot receive entry events. Auto-reconnect is a prerequisite for all event-driven features.
- **VAD silence detection is optional at launch**: The current 10-second fixed recording is already in production. VAD can be added incrementally without changing the state machine.
- **Screen Wake Lock releases on system stop**: The `WakeLockSentinel.release()` call should be tied to the "Stop System" action, not to page visibility changes (which would release it when the browser goes fullscreen in some modes).

---

## MVP Definition

### Launch With (v1)

Minimum to replace the current two-process VLC + FastAPI setup with a single browser window.

- [ ] **Idle video loop (VIDEO1)** — replaces VLC looping; system looks active
- [ ] **WebSocket entry event reception** — triggers workflow; core integration point
- [ ] **Sequential video playback (VIDEO2–8)** — replaces VLC RC commands
- [ ] **Browser microphone recording → `/api/transcribe`** — replaces `sounddevice`
- [ ] **On-screen text feedback** — replaces VLC marquee
- [ ] **System start/stop via UI + keyboard shortcut** — replaces terminal command
- [ ] **MJPEG live feed display** — replaces existing dashboard
- [ ] **System status display (FPS, uptime, tracks)** — operator health check
- [ ] **Screen Wake Lock** — prevents sleep during clinic hours
- [ ] **Fullscreen mode** — production kiosk appearance
- [ ] **WebSocket auto-reconnect** — required for production reliability
- [ ] **All text in Romanian** — patient-facing system requirement

### Add After Validation (v1.x)

Add once the v1 workflow completes one full clinic day without intervention.

- [ ] **Multi-attempt STT with re-prompt** — trigger: first report of garbled CNP/email in production
- [ ] **VAD silence detection** — trigger: patient complaints about waiting 10 seconds after speaking
- [ ] **Confirmation overlay before data submission** — trigger: first data error reported by clinic staff
- [ ] **Snapshot thumbnails in entry log** — trigger: operator asks "who was that?"
- [ ] **Process restart button** — trigger: first time staff has to call a developer to restart

### Future Consideration (v2+)

Defer until single-language, single-clinic workflow is stable.

- [ ] **Multi-attempt with touchscreen fallback** — only if speech-first proves insufficient for a significant patient segment
- [ ] **Queue number display** — only if clinic adds queue management system
- [ ] **EHR webhook integration** — only when a specific EHR target is identified
- [ ] **Multi-language support (Hungarian, English)** — only if patient demographics require it

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Idle video loop | HIGH | LOW | P1 |
| WebSocket entry event + workflow trigger | HIGH | LOW | P1 |
| Sequential video playback | HIGH | LOW | P1 |
| Browser mic recording + transcribe | HIGH | MEDIUM | P1 |
| On-screen STT feedback | HIGH | LOW | P1 |
| System start/stop + keyboard shortcuts | HIGH | MEDIUM | P1 |
| MJPEG live feed | HIGH | LOW | P1 |
| Screen Wake Lock | HIGH | LOW | P1 |
| Fullscreen / kiosk mode | HIGH | LOW | P1 |
| WebSocket auto-reconnect | HIGH | LOW | P1 |
| System status display | MEDIUM | LOW | P1 |
| Entry event log table | MEDIUM | LOW | P2 |
| Manual trigger button | MEDIUM | LOW | P2 |
| Snapshot thumbnails in log | LOW | LOW | P2 |
| Multi-attempt STT with retry | HIGH | MEDIUM | P2 |
| VAD silence detection | MEDIUM | MEDIUM | P2 |
| Confirmation overlay | MEDIUM | MEDIUM | P2 |
| Process restart button | MEDIUM | MEDIUM | P2 |
| Touchscreen fallback | LOW | HIGH | P3 |
| EHR integration | LOW | HIGH | P3 |
| Queue number display | LOW | LOW | P3 |
| Multi-language support | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch — replaces current system completely
- P2: Should have — add when core workflow is validated
- P3: Nice to have — future consideration after production stability

---

## Competitor Feature Analysis

This project is a custom system, not a commercial product. The relevant "competitors" are the tools it replaces and adjacent commercial solutions.

| Feature | Current VLC + FastAPI Setup | Commercial Kiosk (Clearwave, Phreesia) | This Project |
|---------|----------------------------|-----------------------------------------|--------------|
| Video playback | VLC RC socket (unreliable, requires sleep() hacks) | Pre-recorded video or animated UI | HTML5 `<video>` — event-driven, no timing hacks |
| STT | sounddevice + Faster Whisper (offline) | Cloud STT (Nuance, Google) | Web Audio API → Faster Whisper (offline) |
| Detection trigger | Webhook from Python → Flask HTTP | Barcode scan / QR code / touchscreen tap | Webhook from Python → WebSocket broadcast |
| Sleep prevention | caffeinate / powercfg (OS-level) | Dedicated hardware kiosk | Screen Wake Lock API (browser-native) |
| Operator control | SSH terminal | Web admin portal | Single-window browser UI with keyboard shortcuts |
| Monitoring | Separate FastAPI dashboard tab | Separate admin console | Same window, toggled by keyboard shortcut |
| Deployment | Two processes (main.py + controller.py) | SaaS / managed hardware | One FastAPI server + one browser window |
| Cost | Local hardware, no subscription | $200–500/month per location | One-time build cost |
| Privacy | Fully offline | Cloud-dependent | Fully offline — no patient data leaves the LAN |

---

## Sources

- MDN Screen Wake Lock API (HIGH confidence): https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API
- Chrome Wake Lock API (HIGH confidence): https://developer.chrome.com/docs/capabilities/web-apis/wake-lock
- Web Speech API MDN (HIGH confidence — but NOT recommended for this project): https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- FastAPI WebSocket patterns for live dashboards (MEDIUM confidence): https://medium.com/@connect.hashblock/10-fastapi-websocket-patterns-for-live-dashboards-3e36f3080510
- YOLO + FastAPI + WebSocket real-time dashboard (MEDIUM confidence): https://alpha2phi.medium.com/yolo-using-fastapi-websocket-and-react-2b2d28e9f7ed
- MJPEG stream browser performance (MEDIUM confidence): https://github.com/rctoris/mjpegcanvasjs
- Chromium kiosk mode technical guide (MEDIUM confidence): https://smartupworld.com/chromium-kiosk-mode/
- VoiceStreamAI — chunked Whisper + WebSocket mic streaming (MEDIUM confidence): https://github.com/alesaccoia/VoiceStreamAI
- Faster Whisper VAD filter (HIGH confidence — already in codebase): `vad_filter=True` in `controller.py`
- Clearwave kiosk features (LOW confidence, market context): https://www.clearwaveinc.com/patient-check-in-kiosk/
- Phreesia patient check-in (LOW confidence, market context): https://www.phreesia.com/patient-check-in/
- Existing codebase: `dashboard/web.py`, `controller.py`, `.planning/PROJECT.md` (HIGH confidence — primary source)

---
*Feature research for: clinic kiosk web platform (unified Vite frontend)*
*Researched: 2026-03-05*
