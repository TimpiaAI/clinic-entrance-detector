# Codebase Analysis: Clinic Entrance Detector

**Analysis Date:** 2026-03-04

---

## 1. System Overview

The repository contains **two distinct systems** sharing the same directory:

### System A: Vision-Based Entrance Detector (main.py)
A production-grade computer vision system that watches a clinic entrance camera, tracks people with YOLOv8 + BoT-SORT, and triggers webhooks when a person genuinely enters (as opposed to passing by). This is a well-architected, modular Python application.

### System B: VLC Video Controller with STT (controller.py)
A separate, newer script that plays pre-recorded video sequences through VLC (via its RC socket interface), records speech from a microphone, transcribes it with Faster Whisper, and accepts webhook triggers via Flask. This is a single-file prototype for a clinic kiosk/reception workflow.

These two systems are **completely independent** -- they share no code, no imports, no configuration. `controller.py` does not import from `main.py` or any of the project's modules.

---

## 2. Architecture Analysis

### System A: Vision Detector

**Architecture Pattern:** Layered pipeline with event-driven webhook delivery

**Data Flow:**
```
Camera/RTSP/File -> VideoStream (threaded reader)
    -> PersonTracker (YOLOv8 + BoT-SORT)
    -> EntryAnalyzer (dual-zone scoring + classification)
    -> WebhookSender (async queue + retries)
    -> DashboardServer (FastAPI + WebSocket)
```

**Key Files:**

| File | Purpose | Lines |
|------|---------|-------|
| `main.py` | Entry point, main loop, CLI args, overlay drawing | 486 |
| `config.py` | Settings dataclass, .env loading, backward-compat constants | 197 |
| `detector/person_tracker.py` | YOLOv8 + BoT-SORT wrapper | 98 |
| `detector/entry_analyzer.py` | Dual-zone scoring, classification, event emission | 615 |
| `detector/zone_config.py` | Calibration data models, JSON persistence | 148 |
| `webhook/sender.py` | Async httpx sender with retries, cooldowns, HMAC | 217 |
| `dashboard/web.py` | FastAPI dashboard, MJPEG stream, WebSocket, calibration API | 271 |
| `calibration/calibration_tool.py` | Interactive OpenCV calibration UI | 164 |
| `utils/video_stream.py` | Threaded video capture abstraction | 107 |
| `utils/snapshot.py` | JPEG encoding + base64 for webhook payloads | 41 |
| `utils/logger.py` | JSON-formatted structured logging | 40 |
| `training/data_collector.py` | Interactive dataset collection with OpenCV UI | 304 |
| `training/trainer.py` | YOLO fine-tuning wrapper | 111 |

**Layer Separation:**
- Detection layer (`detector/`) has clean interfaces; `PersonTracker` returns `TrackedPerson` dataclasses, `EntryAnalyzer` returns `EntryEvent` dataclasses
- Webhook layer (`webhook/`) is fully decoupled via an async queue
- Dashboard (`dashboard/`) receives state through a thread-safe `DashboardState` object
- Configuration is centralized in `config.py` with env-var loading

**Threading Model:**
- Main thread: detection loop (read frame -> track -> analyze -> draw)
- Video reader thread: `VideoStream._reader_loop()` captures frames independently
- Webhook thread: runs its own asyncio event loop (`WebhookSender._thread_main()`)
- Dashboard thread: Uvicorn server (`DashboardServer.start()`)

### System B: VLC Controller

**Architecture Pattern:** Sequential state machine in a single file

**Data Flow:**
```
Flask /trigger webhook -> threading.Event
    -> idle_loop breaks
    -> Sequential video playback (VIDEO1-8) via VLC RC socket
    -> Speech recording (sounddevice) + transcription (Faster Whisper)
    -> Marquee text overlay via VLC RC commands
    -> Loop back to idle
```

**Key File:** `controller.py` (312 lines, everything in one file)

**Components within controller.py:**
- VLC process launcher (`_launch_vlc()`)
- RC socket client (`_rc_connect()`, `_rc_cmd()`)
- Video playback helpers (`play_video()`, `play_video_for()`, `play_video_loop()`)
- Marquee text overlay (`show_marquee()`, `hide_marquee()`)
- Speech recording + transcription (`speech()`)
- Combined play+STT workflow (`play_video_then_stt()`)
- Main workflow state machine (`workflow()`)
- Flask webhook server (`app`, `server()`)

---

## 3. Technology Stack

### System A Dependencies (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| ultralytics | >=8.3.0 | YOLOv8 object detection + tracking |
| opencv-python | >=4.9.0 | Video capture, image processing, overlays |
| numpy | >=1.24.0 | Array operations |
| supervision | >=0.25.0 | Polygon zone containment checks |
| fastapi | >=0.109.0 | Dashboard web framework |
| uvicorn | >=0.27.0 | ASGI server for dashboard |
| websockets | >=12.0 | Real-time dashboard updates |
| jinja2 | >=3.1.0 | HTML template rendering |
| httpx | >=0.27.0 | Async HTTP client for webhooks |
| python-dotenv | >=1.0.0 | .env file loading |
| python-multipart | >=0.0.6 | FastAPI form handling |

### System B Dependencies (imported but NOT in requirements.txt)

| Package | Purpose |
|---------|---------|
| flask | Webhook server (port 5050) |
| sounddevice | Microphone audio recording |
| scipy.io.wavfile | WAV file writing |
| faster-whisper | Speech-to-text (Whisper medium model, int8) |
| numpy | Audio normalization |

**Critical gap:** `controller.py` dependencies (flask, sounddevice, scipy, faster-whisper) are NOT listed in `requirements.txt`.

### Runtime Requirements

- **Python:** 3.11+ (Dockerfile uses 3.11-slim; local .venv uses 3.14)
- **System:** ffprobe (used by controller.py for video duration), VLC (macOS path hardcoded)
- **Hardware:** CPU sufficient for YOLOv8m at 1280px; USB webcam or RTSP camera
- **External:** VLC.app at `/Applications/VLC.app/Contents/MacOS/VLC` (controller.py only)

### Configuration

- `.env` file loaded by python-dotenv (exists but gitignored)
- `.env.minipc` alternate config file (exists but gitignored -- likely for deployment target)
- `config.env.example` provides template with all 30+ settings
- `calibration.json` stores zone/tripwire geometry
- `botsort_tuned.yaml` custom tracker configuration

---

## 4. Code Quality Assessment

### Strengths

**System A (Vision Detector):**
1. **Clean architecture** -- well-separated layers with dataclass interfaces between them
2. **Thread safety** -- `DashboardState` uses locks, `WebhookSender` uses asyncio queue + lock-protected cooldowns
3. **Robust webhook delivery** -- exponential backoff retries, per-person and global cooldowns, HMAC signing, failed event persistence to JSONL
4. **Structured logging** -- JSON formatter for machine-readable logs
5. **Graceful shutdown** -- signal handlers, webhook queue flush with timeout, stream cleanup
6. **Daily counter rotation** -- auto-resets at midnight UTC
7. **Anti-duplication** -- per-ID cooldown prevents double-counting
8. **Graduated scoring** -- partial credit system avoids brittle binary thresholds
9. **Type annotations** -- consistent use of `from __future__ import annotations`, dataclasses with `slots=True`
10. **Dual-zone approach** -- Zone A (approach) + Zone B (commitment) with temporal ordering is a sophisticated detection strategy

**System B (Controller):**
1. **Simple and focused** -- single-file approach is appropriate for a kiosk controller prototype
2. **Email reconstruction** -- regex-based Romanian speech-to-email conversion handles common transcription errors
3. **CNP detection** -- automatically strips non-digits when 10+ digits detected

### Weaknesses and Concerns

#### System B: controller.py -- Major Issues

**1. VLC RC Socket Reliability (HIGH IMPACT)**
- File: `controller.py`, lines 39-89
- The VLC RC (remote control) interface is a telnet-like text protocol over TCP. It is inherently unreliable:
  - Commands have no acknowledgment protocol -- `_rc_cmd()` sends a command, sleeps 150ms, then tries to read a response. This is a race condition.
  - Socket timeouts of 2 seconds are used but errors are silently swallowed.
  - If VLC crashes or the socket disconnects, there is no reconnection logic. The entire program hangs or crashes.
  - The `_launch_vlc()` function uses a fixed `time.sleep(2)` to wait for VLC to start, which is brittle across different hardware speeds.
- **Fix approach:** Replace VLC RC with python-vlc (libVLC bindings) which provides a proper programmatic API with callbacks, or use mpv with its JSON IPC protocol which is more reliable.

**2. Module-Level Side Effects (HIGH IMPACT)**
- File: `controller.py`, lines 30, 306-311
- The Whisper model loads at import time: `model = WhisperModel("medium", compute_type="int8")` (line 30). This is a ~1.5GB model that takes 10-30 seconds to load.
- VLC launches at module level (lines 306-307): `_vlc_proc = _launch_vlc()` and `_rc_connect()`.
- Flask server and workflow start at module level (lines 310-311).
- This means the file cannot be imported without launching VLC, loading Whisper, and starting everything. It cannot be tested, reused, or composed.
- **Fix approach:** Wrap all initialization in a `main()` function. Use lazy loading for the Whisper model.

**3. Blocking Sleep-Based Synchronization (MEDIUM IMPACT)**
- File: `controller.py`, lines 119, 128, 253
- Video playback uses `time.sleep(duration + 0.5)` to wait for videos to finish. If VLC playback stalls or the duration is wrong, the workflow proceeds regardless.
- There is no way to interrupt playback (e.g., if a new webhook arrives during a video sequence).
- **Fix approach:** Poll VLC's playback state or use python-vlc's MediaPlayer events.

**4. Hardcoded VLC Path (LOW IMPACT)**
- File: `controller.py`, line 33
- `VLC_PATH = "/Applications/VLC.app/Contents/MacOS/VLC"` -- macOS-only, not configurable
- **Fix approach:** Use environment variable or config, with platform detection fallback.

**5. No Error Recovery in Workflow (HIGH IMPACT)**
- File: `controller.py`, lines 261-284
- The `workflow()` function is an infinite loop with no try/except. Any exception (VLC crash, audio device error, transcription failure) kills the entire program.
- Speech recording failure (no microphone, device busy) crashes everything.
- **Fix approach:** Wrap each step in try/except with logging and recovery.

**6. Global Mutable State (MEDIUM IMPACT)**
- File: `controller.py`, lines 25, 36
- `trigger_event = threading.Event()` and `_rc_sock = None` are module-level globals.
- **Fix approach:** Encapsulate in a class.

#### System A: Moderate Concerns

**7. Overlay Drawing in main.py (LOW-MEDIUM IMPACT)**
- File: `main.py`, lines 94-252
- 160 lines of OpenCV drawing code lives in `main.py` rather than a dedicated overlay/visualization module. This makes `main.py` harder to maintain.
- **Fix approach:** Extract to `utils/overlay.py` or `visualization.py`.

**8. Backward-Compatible Constants (LOW IMPACT)**
- File: `config.py`, lines 163-197
- 35 lines of `SETTING_NAME = SETTINGS.SETTING_NAME` for backward compatibility. These module-level constants mean settings loaded at import time cannot be overridden later.
- **Fix approach:** Remove if nothing imports them directly, or use property-based access.

**9. Test Files Are Not Unit Tests (MEDIUM IMPACT)**
- Files: `tests/test_with_webcam.py`, `tests/test_with_video.py`
- These are manual integration test scripts that require a camera or video file. There are no automated unit tests, no pytest configuration, no CI integration.
- The test files do not test edge cases in the scoring algorithm, zone containment, or webhook delivery.
- **Fix approach:** Add pytest-based unit tests for `EntryAnalyzer._compute_scores()`, `EntryAnalyzer._classify()`, `WebhookSender` cooldown logic, etc.

**10. MJPEG Stream Generator Never Terminates (LOW IMPACT)**
- File: `dashboard/web.py`, line 131
- `_stream_generator()` is an infinite generator with `time.sleep(0.066)`. If a client disconnects, the generator keeps running until garbage collected. FastAPI/Starlette should handle this, but it could leak threads under load.

**11. Duplicate SourceType Definition (LOW IMPACT)**
- Files: `config.py` line 13, `utils/video_stream.py` line 14
- `SourceType = Literal["webcam", "rtsp", "file"]` is defined in both files.
- **Fix approach:** Define once in `config.py` and import elsewhere.

---

## 5. The Two Systems: Relationship and Integration Gap

### How They Relate
- System A (vision detector) detects people entering the clinic and sends webhooks
- System B (controller) listens for webhooks on `/trigger` and plays a kiosk interaction sequence (greeting video, name/CNP/email speech recording)
- The intended flow: System A detects entry -> webhook -> System B starts kiosk interaction

### Integration Gap
- System A sends webhooks to `WEBHOOK_URL` (configurable). System B listens on `0.0.0.0:5050/trigger`.
- System A's webhook payload contains rich data (person_id, confidence, snapshot). System B ignores the payload entirely -- it just calls `trigger_event.set()`.
- There is no shared configuration or service discovery between them.
- System B's dependencies are not in `requirements.txt`.

### The Kiosk Workflow (controller.py)
1. Loop VIDEO1 (idle/welcome screen)
2. Webhook arrives -> play VIDEO2 (greeting)
3. Play VIDEO3 -> record speech (patient name)
4. Play VIDEO6 -> record speech (unknown prompt)
5. Play VIDEO7 -> record speech (CNP number, with digit prompt)
6. Play VIDEO8 -> record speech (email address, with Romanian email prompt)
7. Play VIDEO4 (thank you/confirmation)
8. Play VIDEO1 for 5 seconds
9. Play VIDEO5 (goodbye?)
10. Return to idle loop

### Speech Transcription Details
- Uses Faster Whisper with `medium` model, `int8` quantization
- Records 10 seconds of audio at 16kHz mono
- VAD filter enabled
- Romanian language (`language="ro"`)
- CNP detection: if transcription contains 10+ digits, strip to digits only
- Email detection: regex replacement of Romanian speech patterns for "at" and "dot" (`arond`/`arung` -> `@`, `punct`/`dot` -> `.`)

---

## 6. Deployment Architecture

### Docker
- `Dockerfile`: Python 3.11-slim, installs libgl1 + libglib2.0 for OpenCV, exposes port 8080
- `docker-compose.yml`: mounts `/dev/video0`, `.env`, `calibration.json`, logs volume

### Systemd
- `deploy/clinic-entrance-detector.service`: runs as simple service under `/opt/clinic-entrance-detector/`
- Logs to `/var/log/clinic-entrance-detector.log`
- Auto-restart with 5s delay

### Note
Docker and systemd configs are for System A only. System B (controller.py) has no deployment configuration.

---

## 7. Specific Recommendations for controller.py Rewrite

The controller.py file is the active development target. Here are prioritized recommendations:

### P0: Replace VLC RC with python-vlc or mpv IPC
- The RC socket approach is the single biggest reliability risk
- python-vlc provides `MediaPlayer.event_manager()` for end-of-media callbacks
- mpv's `--input-ipc-server` provides a JSON-based protocol with proper request/response semantics
- Alternative: use pygame or similar for video playback with direct control

### P1: Add error handling around every I/O operation
- Speech recording can fail (no mic, device busy, permissions)
- VLC can crash mid-playback
- Whisper transcription can fail (corrupted audio, model error)
- Each step needs try/except with graceful fallback

### P2: Make the workflow interruptible
- Currently, if a new webhook arrives during the workflow, it is ignored until the current cycle completes
- Consider using a state machine with event-driven transitions instead of blocking sleeps

### P3: Extract configuration
- Video file paths should be configurable (env vars or config file)
- VLC path should be configurable
- Recording duration, sample rate, Whisper model should be configurable
- Flask port should be configurable

### P4: Store transcription results
- Currently, speech results are printed to stdout but never stored or sent anywhere
- The system needs to POST results to a backend or store them locally

### P5: Add the controller's dependencies to requirements
- flask, sounddevice, scipy, faster-whisper need to be in requirements.txt (or a separate requirements-controller.txt)

---

## 8. File Structure Summary

```
clinic-entrance-detector/
├── main.py                          # System A: Vision detector entry point + main loop
├── controller.py                    # System B: VLC kiosk controller (UNTRACKED in git)
├── config.py                        # System A: Settings dataclass + .env loading
├── requirements.txt                 # System A dependencies only
├── .env                             # Environment config (gitignored)
├── .env.minipc                      # Alternate env for mini PC deployment (gitignored)
├── config.env.example               # Template for .env
├── calibration.json                 # Zone/tripwire calibration data
├── botsort_tuned.yaml               # Custom BoT-SORT tracker config
├── detector/
│   ├── __init__.py
│   ├── person_tracker.py            # YOLOv8 + BoT-SORT tracking wrapper
│   ├── entry_analyzer.py            # Dual-zone scoring + event classification
│   └── zone_config.py               # Calibration data models + JSON I/O
├── webhook/
│   ├── __init__.py
│   └── sender.py                    # Async webhook delivery with retries
├── dashboard/
│   ├── __init__.py
│   ├── web.py                       # FastAPI dashboard server
│   └── templates/
│       ├── index.html               # Live monitoring dashboard
│       └── calibrate.html           # Web calibration tool
├── calibration/
│   ├── __init__.py
│   └── calibration_tool.py          # Interactive OpenCV calibration
├── utils/
│   ├── __init__.py
│   ├── video_stream.py              # Threaded video capture
│   ├── snapshot.py                  # JPEG encoding for webhooks
│   └── logger.py                    # JSON structured logging
├── training/
│   ├── __init__.py
│   ├── data_collector.py            # Interactive dataset collection
│   └── trainer.py                   # YOLO fine-tuning wrapper
├── tests/
│   ├── test_with_webcam.py          # Manual webcam integration test
│   └── test_with_video.py           # Manual video file test
├── deploy/
│   └── clinic-entrance-detector.service  # Systemd unit file
├── Dockerfile                       # Docker build for System A
├── docker-compose.yml               # Docker Compose for System A
├── .gitignore
├── README.md                        # Project documentation
├── CLINIC_ENTRANCE_DETECTOR_DOCS.md # Extended technical docs (85KB)
├── yolov8m.pt                       # YOLO medium model weights (gitignored)
├── yolov8n.pt                       # YOLO nano model weights (gitignored)
├── video1.mp4 - video8.mp4          # Kiosk video files (UNTRACKED)
├── speech.wav                        # Last recorded speech (UNTRACKED)
└── webhook_failed_events.jsonl       # Failed webhook payloads (gitignored)
```

---

## 9. Detection Algorithm Summary (System A)

### Scoring (max 1.0)
- **Bbox growth** (0-0.25): Linear ramp from ratio 1.0 to BBOX_GROWTH_RATIO threshold
- **Directional movement** (0-0.20): Linear ramp to Y_MOVEMENT_THRESHOLD pixels
- **Dwell time** (0-0.10): Ramp from 0 to DWELL_TIME_MIN, flat until DWELL_TIME_MAX
- **Tripwire crossing** (0 or 0.10): Binary bonus
- **Zone crossing** (0-0.25): Zone A -> Zone B with >=5 consecutive Zone B frames
- **Velocity consistency** (0-0.10): Fraction of position steps in entry direction

### Classification Rules
1. **entering**: (Zone A seen -> Zone B seen, >=5 Zone B frames, score >= threshold, dwell <= max, velocity >= 0.3) OR (tripwire crossed, score >= threshold+0.1, track age >= 1s, velocity >= 0.4)
2. **exiting**: bbox shrinking (ratio <= 0.85) + reverse movement
3. **passing**: low dwell + low movement
4. **loitering**: dwell > DWELL_TIME_MAX
5. **unknown**: default / track too young (< 0.5s)

---

*Analysis completed: 2026-03-04*
