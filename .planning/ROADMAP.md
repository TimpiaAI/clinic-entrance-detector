# Roadmap: Clinic Entrance Detector — Web Platform

## Overview

Six phases build from the bottom up: stable backend endpoints first, then a frontend foundation that proves the dev environment works, then video and audio pipelines as independent verticals, then the workflow state machine that wires everything together, and finally kiosk hardening for production deployment. Each phase can be validated independently before the next begins — video bugs stay in Phase 3, audio bugs stay in Phase 4, and the Phase 5 state machine starts on a solid base.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Backend Extensions** - Extend FastAPI with process management, transcription, sleep prevention, and video serving endpoints
- [ ] **Phase 2: Frontend Foundation** - Scaffold Vite frontend with live detection feed, status display, entry log, and keyboard shortcuts
- [ ] **Phase 3: Video Overlay** - HTML5 video playback system replacing VLC — idle loop, sequential instructional video playback, text overlays
- [ ] **Phase 4: Audio Pipeline** - Browser microphone capture, Whisper transcription, and CNP/email extraction end-to-end
- [ ] **Phase 5: Workflow State Machine** - Complete patient interaction cycle from entry detection to data submission, with system controls
- [ ] **Phase 6: Kiosk Hardening** - Production deployment — Chrome kiosk mode, two-layer sleep prevention, Windows 11 validation

## Phase Details

### Phase 1: Backend Extensions
**Goal**: All backend endpoints exist and are testable with curl before any JavaScript is written
**Depends on**: Nothing (first phase)
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06, BACK-07, BACK-08
**Success Criteria** (what must be TRUE):
  1. `curl -X POST localhost:8080/api/process/start` starts the detector subprocess and camera feed appears
  2. `curl -X POST localhost:8080/api/process/stop` cleanly stops detector with no orphan processes holding the camera (verified by immediate re-start succeeding)
  3. `curl -F "audio=@test.webm" localhost:8080/api/transcribe` returns a JSON response with `text`, `cnp`, and `email` fields
  4. `curl localhost:8080/api/videos/video1.mp4` streams the video file with HTTP 206 range support (browser can seek)
  5. `curl -X POST localhost:8080/api/system/wake-lock` activates sleep prevention; OS-level confirmation visible (caffeinate on macOS, SetThreadExecutionState on Windows)
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Process manager: subprocess start/stop/status with psutil tree kill
- [x] 01-02-PLAN.md — Transcription endpoint: Whisper lazy-load, CNP/email extraction from Romanian speech
- [x] 01-03-PLAN.md — Wake-lock, video serving with HTTP 206, StaticFiles mount, DashboardState extension

### Phase 2: Frontend Foundation
**Goal**: Browser displays live detection feed with status and keyboard shortcuts working — dev environment fully validated
**Depends on**: Phase 1
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06, KEYS-01, KEYS-02, KEYS-03, KEYS-04, KEYS-05, KIOSK-02, KIOSK-03, KIOSK-04, KIOSK-06
**Success Criteria** (what must be TRUE):
  1. Browser shows a live camera feed with bounding boxes, zones, and tripwire overlays — rendered via fetch-to-canvas (not `<img>` tag) with no memory growth over 30 minutes
  2. Status panel updates in real-time showing FPS, active tracks, total entries today, uptime, and webhook status — values change as the detector runs
  3. Entry log table gains a new row within 1 second of a real detection event, showing timestamp, person ID, confidence, and snapshot thumbnail — without page refresh
  4. Pressing F3 toggles detection overlay visibility on/off; F4 fires a test entry event; Escape halts operation — all confirmed with `event.code` not `keypress`
  5. Vite dev server proxies WebSocket and MJPEG to the FastAPI backend with no connection errors — `ws: true` confirmed in vite.config.ts
  6. All UI text appears in Romanian — no English strings visible in the interface
**Plans:** 3 plans

Plans:
- [ ] 02-01-PLAN.md — Vite scaffold, MJPEG fetch-to-canvas renderer, WebSocket with exponential backoff reconnect
- [ ] 02-02-PLAN.md — Status panel, entry log table with real-time WebSocket updates, snapshot thumbnails
- [ ] 02-03-PLAN.md — Keyboard shortcut bindings (F2/F3/F4/Escape), Romanian UI strings, API wrappers

### Phase 3: Video Overlay
**Goal**: Instructional videos play reliably in the browser over the camera feed, with idle loop and text overlays
**Depends on**: Phase 2
**Requirements**: VCTL-01, VCTL-02, VCTL-03, VCTL-04, VCTL-05
**Success Criteria** (what must be TRUE):
  1. video1.mp4 loops continuously as an idle screen with no blank frames or playback interruptions
  2. A simulated `person_entered` webhook event causes the browser to play the instructional video sequence — each video transitions on `onended`, not on a timer
  3. Text overlays (marquee) appear on top of the video during playback with correct Romanian labels
  4. The camera feed remains visible (behind the video layer) when no video is playing — hiding the video uses CSS opacity, not src reassignment
  5. Video autoplay works on first Chrome kiosk cold-boot with no prior user interaction (verified with `--autoplay-policy=no-user-gesture-required` flag in test launch)
**Plans**: TBD

Plans:
- [ ] 03-01: CSS z-index layout (feed / video / text overlay layers), idle loop, video.ts with play/pause/hide controls
- [ ] 03-02: Webhook-triggered playback, onended transitions, marquee text overlay, autoplay validation

### Phase 4: Audio Pipeline
**Goal**: Microphone captures speech, backend transcribes in Romanian, and CNP/email extraction works end-to-end
**Depends on**: Phase 3
**Requirements**: STT-01, STT-02, STT-03, STT-04, STT-05, STT-06
**Success Criteria** (what must be TRUE):
  1. Clicking "Start System" requests microphone permission — the browser prompt appears and permission is granted from localhost
  2. Speaking Romanian into the microphone and triggering a recording produces a transcription result displayed on screen within 10 seconds
  3. Speaking a valid CNP (13 digits) causes the backend to return it extracted correctly in the `cnp` field
  4. Speaking an email address causes the backend to return it extracted correctly in the `email` field
  5. The operator sees a "Procesare..." loading state during transcription and the result with a confirmation prompt before it is accepted
  6. AudioContext is created inside the "Start System" gesture handler — recording never fails silently due to suspended AudioContext
**Plans**: TBD

Plans:
- [ ] 04-01: audio.ts — getUserMedia, MediaRecorder stop-and-collect, PCM-to-WAV conversion, POST to /api/transcribe
- [ ] 04-02: Transcription result display, confirmation prompt UI, AudioContext lifecycle guard, mic permission flow validation

### Phase 5: Workflow State Machine
**Goal**: Complete patient interaction cycle runs end-to-end — entry detected, videos play, data captured, system can be started and stopped
**Depends on**: Phase 4
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04, WKFL-05, CTRL-01, CTRL-02, CTRL-03, CTRL-04, CTRL-05
**Success Criteria** (what must be TRUE):
  1. A person walking past the camera triggers the full workflow: idle -> greeting -> ask_name -> record -> show -> ask_cnp -> record -> show -> ask_email -> record -> confirm -> submit -> farewell -> idle — completing without operator intervention
  2. If a patient does not respond within the timeout window, the system returns to idle automatically with all captured data cleared
  3. The confirmation step displays all captured name, CNP, and email — and only submits the webhook after the patient confirms
  4. Pressing Start (F2 / UI button) starts the detector and activates the system; pressing Stop or Escape halts all processes immediately
  5. If the detector process crashes, the operator sees an alert in the UI with a Restart button — no SSH required to recover
**Plans**: TBD

Plans:
- [ ] 05-01: workflow.ts state machine (all states, transitions, timeout handling), person_entered WebSocket trigger
- [ ] 05-02: CTRL-01 to CTRL-05 — start/stop UI button, process health monitoring, crash recovery alert, F2/Escape bindings wired to process manager

### Phase 6: Kiosk Hardening
**Goal**: System runs reliably in production on Windows 11 Pro — never sleeps, never shows browser chrome, survives 24/7 operation
**Depends on**: Phase 5
**Requirements**: CTRL-06, KIOSK-01, KIOSK-05
**Success Criteria** (what must be TRUE):
  1. Launching the Chrome kiosk script on Windows 11 Pro opens the app fullscreen with no URL bar, no address bar, no error dialogs — and the first video plays with no user interaction
  2. After 2 hours of idle operation, the screen has not dimmed or locked — both Screen Wake Lock (browser) and wakepy (OS-level) are active simultaneously
  3. If the tab is temporarily hidden (e.g., Alt+Tab), the wake lock is re-acquired within 2 seconds of the tab becoming visible again
  4. The complete workflow (entry detection -> video -> recording -> confirm -> submit -> idle) runs successfully on Windows 11 Pro with the same result as macOS development
**Plans**: TBD

Plans:
- [ ] 06-01: Chrome kiosk launch script (all required flags), two-layer sleep prevention (Screen Wake Lock + wakepy), visibilitychange re-acquisition listener
- [ ] 06-02: Windows 11 Pro full workflow validation — camera lock, audio device, mic permissions, path separators, entry log DOM performance at 100 rows

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Extensions | 3/3 | Complete | 2026-03-05 |
| 2. Frontend Foundation | 0/3 | Planning complete | - |
| 3. Video Overlay | 0/2 | Not started | - |
| 4. Audio Pipeline | 0/2 | Not started | - |
| 5. Workflow State Machine | 0/2 | Not started | - |
| 6. Kiosk Hardening | 0/2 | Not started | - |
