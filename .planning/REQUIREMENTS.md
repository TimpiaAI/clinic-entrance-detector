# Requirements: Clinic Entrance Detector — Web Platform

**Defined:** 2026-03-05
**Core Value:** When activated, the system reliably detects clinic entries, plays instructional videos, and captures patient data — all from a single browser window that never lets the computer sleep.

## v1 Requirements

Requirements for the unified web platform release. Each maps to roadmap phases.

### System Control

- [x] **CTRL-01**: Operator can start/stop the entire system (detector + workflow) with a single button click
- [x] **CTRL-02**: Operator can emergency-stop everything with a dedicated keyboard shortcut (Escape key)
- [x] **CTRL-03**: System auto-starts the detection pipeline when the web app loads
- [x] **CTRL-04**: Web app monitors detector process health and shows status (running/stopped/crashed)
- [x] **CTRL-05**: If detector process crashes, web app displays alert and offers restart
- [ ] **CTRL-06**: Computer does not sleep or turn off screen while system is active (Screen Wake Lock + OS-level wakepy)

### Video Feed & Detection Display

- [x] **FEED-01**: Browser displays live MJPEG camera feed with bounding boxes, zones, and tripwire overlays
- [x] **FEED-02**: Operator can toggle detection overlay visibility on/off via keyboard shortcut
- [x] **FEED-03**: Entry log table shows detected entries with timestamp, person ID, confidence score, and snapshot thumbnail
- [x] **FEED-04**: Status panel displays real-time metrics: FPS, active tracked people, total entries today, uptime, webhook status
- [x] **FEED-05**: Entry log table updates in real-time via WebSocket (no page refresh needed)
- [x] **FEED-06**: Manual trigger keyboard shortcut fires a test entry event (for debugging)

### Video Controller

- [x] **VCTL-01**: 8 instructional videos (video1-8.mp4) play in the same browser window overlaid on the camera feed
- [x] **VCTL-02**: Video playback is triggered automatically by entrance detection webhook events
- [x] **VCTL-03**: Idle video loops continuously when no patient workflow is active
- [x] **VCTL-04**: Text overlays (marquee) display extracted patient data during video playback
- [x] **VCTL-05**: Video transitions are event-driven (onended callback), not time-based

### Speech & Data Capture

- [x] **STT-01**: Browser captures audio from microphone via Web Audio API / MediaRecorder
- [x] **STT-02**: Audio is sent to Python backend for Faster Whisper transcription (Romanian language)
- [x] **STT-03**: Backend extracts CNP (Romanian national ID number) from transcribed speech
- [x] **STT-04**: Backend extracts email address from transcribed speech
- [x] **STT-05**: Transcription results are displayed to operator/patient with confirmation step
- [x] **STT-06**: Microphone permission is requested on operator's "Start System" gesture (user interaction required)

### Workflow State Machine

- [x] **WKFL-01**: Full patient workflow cycle: idle -> greeting -> ask_name -> record -> show -> ask_cnp -> record -> show -> ask_email -> record -> confirm -> submit -> farewell -> idle
- [x] **WKFL-02**: Each workflow state has a timeout that returns to idle if exceeded (patient abandonment)
- [x] **WKFL-03**: Captured patient data is cleared on timeout or workflow completion
- [x] **WKFL-04**: Workflow submits collected data via webhook on confirmation
- [x] **WKFL-05**: Confirmation step shows all captured data and asks patient to verify

### Keyboard Shortcuts

- [x] **KEYS-01**: Start/Stop system toggle (configurable key, default: F2)
- [x] **KEYS-02**: Toggle detection overlay visibility (default: F3)
- [x] **KEYS-03**: Manual trigger test entry event (default: F4)
- [x] **KEYS-04**: Emergency stop — halt all processes immediately (default: Escape)
- [x] **KEYS-05**: All keyboard shortcuts use `keydown` with `event.code` (not deprecated `keypress`)

### Kiosk & Platform

- [ ] **KIOSK-01**: Web app runs in Chrome kiosk mode (fullscreen, no URL bar) on production
- [x] **KIOSK-02**: Web app runs in normal browser mode for development with DevTools access
- [x] **KIOSK-03**: All UI text is in Romanian language (hardcoded, no i18n framework)
- [x] **KIOSK-04**: App works on Windows 11 Pro (production) and macOS (development) without code changes
- [ ] **KIOSK-05**: Chrome launch script with kiosk flags (--kiosk, --noerrdialogs, --disable-session-crashed-bubble, --autoplay-policy=no-user-gesture-required)
- [x] **KIOSK-06**: Frontend is built with Vite and served by FastAPI StaticFiles in production

### Backend Extensions

- [x] **BACK-01**: FastAPI serves Vite-built frontend via StaticFiles mount
- [x] **BACK-02**: POST /api/process/start starts the detector subprocess
- [x] **BACK-03**: POST /api/process/stop stops the detector subprocess (with psutil tree kill on Windows)
- [x] **BACK-04**: GET /api/process/status returns detector process state
- [x] **BACK-05**: POST /api/transcribe accepts audio blob (WebM), transcribes with Faster Whisper, returns text + extracted CNP/email
- [x] **BACK-06**: GET /api/videos/:id serves instructional video files with HTTP range request support
- [x] **BACK-07**: POST /api/system/wake-lock activates wakepy sleep prevention
- [x] **BACK-08**: POST /api/system/wake-lock/release deactivates wakepy sleep prevention

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Detection

- **DET-01**: Multi-camera support from single web interface
- **DET-02**: Historical entry analytics and charts
- **DET-03**: Export entry log to CSV/Excel

### Enhanced Kiosk

- **KIOSK-07**: Touchscreen keyboard fallback for email input
- **KIOSK-08**: Fine-tuned Romanian Whisper model (gigant/whisper-medium-romanian)
- **KIOSK-09**: Auto-update mechanism for video content

### Remote Management

- **MGMT-01**: Remote monitoring dashboard for multiple clinic locations
- **MGMT-02**: Remote configuration changes

## Out of Scope

| Feature | Reason |
|---------|--------|
| Detection algorithm changes | Works perfectly — YOLOv8 + BoT-SORT + dual-zone scoring is production-proven |
| Mobile app | Desktop kiosk only — single screen, keyboard-operated |
| Multi-camera support | Single camera per instance; defer to v2 |
| Cloud deployment | Runs on local mini PC, no internet required |
| User authentication | Single operator, local network only |
| HTTPS/TLS | Local-only deployment; localhost is treated as secure context by Chrome |
| React/Vue/Angular framework | Overkill for single-screen kiosk with ~5 DOM elements |
| Electron wrapper | Chrome --kiosk is sufficient; Electron adds 150-200MB overhead |
| i18n framework | Romanian only — hardcode strings directly |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BACK-01 | Phase 1 | Complete |
| BACK-02 | Phase 1 | Complete |
| BACK-03 | Phase 1 | Complete |
| BACK-04 | Phase 1 | Complete |
| BACK-05 | Phase 1 | Complete |
| BACK-06 | Phase 1 | Complete |
| BACK-07 | Phase 1 | Complete |
| BACK-08 | Phase 1 | Complete |
| FEED-01 | Phase 2 | Complete |
| FEED-02 | Phase 2 | Complete |
| FEED-03 | Phase 2 | Complete |
| FEED-04 | Phase 2 | Complete |
| FEED-05 | Phase 2 | Complete |
| FEED-06 | Phase 2 | Complete |
| KEYS-01 | Phase 2 | Complete |
| KEYS-02 | Phase 2 | Complete |
| KEYS-03 | Phase 2 | Complete |
| KEYS-04 | Phase 2 | Complete |
| KEYS-05 | Phase 2 | Complete |
| KIOSK-02 | Phase 2 | Complete |
| KIOSK-03 | Phase 2 | Complete |
| KIOSK-04 | Phase 2 | Complete |
| KIOSK-06 | Phase 2 | Complete |
| VCTL-01 | Phase 3 | Complete |
| VCTL-02 | Phase 3 | Complete |
| VCTL-03 | Phase 3 | Complete |
| VCTL-04 | Phase 3 | Complete |
| VCTL-05 | Phase 3 | Complete |
| STT-01 | Phase 4 | Complete |
| STT-02 | Phase 4 | Complete |
| STT-03 | Phase 4 | Complete |
| STT-04 | Phase 4 | Complete |
| STT-05 | Phase 4 | Complete |
| STT-06 | Phase 4 | Complete |
| WKFL-01 | Phase 5 | Complete |
| WKFL-02 | Phase 5 | Complete |
| WKFL-03 | Phase 5 | Complete |
| WKFL-04 | Phase 5 | Complete |
| WKFL-05 | Phase 5 | Complete |
| CTRL-01 | Phase 5 | Complete |
| CTRL-02 | Phase 5 | Complete |
| CTRL-03 | Phase 5 | Complete |
| CTRL-04 | Phase 5 | Complete |
| CTRL-05 | Phase 5 | Complete |
| CTRL-06 | Phase 6 | Pending |
| KIOSK-01 | Phase 6 | Pending |
| KIOSK-05 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-05 — traceability populated by roadmapper*
