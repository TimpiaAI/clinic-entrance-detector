# Clinic Entrance Detector — Web Platform

## What This Is

A unified web platform that merges the clinic entrance detection system, instructional video controller, and speech-based patient data capture into a single lightweight browser application. It replaces the current separate VLC controller and FastAPI dashboard with one kiosk-mode web app that auto-manages the entire patient arrival workflow — from detecting someone walking in, to playing instructional videos, recording their responses, and extracting CNP/email data. Built for a clinic reception running on Windows 11 Pro, developed on macOS.

## Core Value

When the operator activates the system, it must reliably detect clinic entries, play the right instructional video, and capture patient data — all from a single browser window that never lets the computer sleep or the screen turn off.

## Requirements

### Validated

<!-- Existing working systems that must be preserved -->

- ✓ Real-time person detection via YOLOv8 + BoT-SORT tracking — existing
- ✓ Dual-zone graduated scoring for entry classification — existing
- ✓ Webhook delivery with async queue, retries, HMAC signing — existing
- ✓ Interactive zone/tripwire calibration — existing
- ✓ MJPEG video stream with detection overlays — existing
- ✓ WebSocket real-time state updates — existing

### Active

<!-- New requirements for the web platform -->

- [ ] Unified Vite frontend replaces FastAPI dashboard and VLC controller
- [ ] One-click system activation auto-starts detector and monitoring
- [ ] Live video feed with bounding boxes, zones, and tripwire overlays in browser
- [ ] Entry log table with timestamp, person ID, confidence, snapshot thumbnail
- [ ] Instructional video playback in same browser window (overlay on detection feed)
- [ ] 8 instructional videos (video1-8.mp4) triggered by entrance detection events
- [ ] Browser microphone recording via Web Audio API
- [ ] Audio sent to Python backend for Faster Whisper transcription
- [ ] CNP (Romanian national ID) and email extraction from transcribed speech
- [ ] Marquee/text overlays on instructional videos
- [ ] Sleep/screen-off prevention (Windows: powercfg, macOS: caffeinate)
- [ ] Keyboard shortcuts: Start/Stop (system toggle), Toggle detection view, Manual trigger, Emergency stop
- [ ] Kiosk mode for production (fullscreen, no URL bar)
- [ ] Normal browser mode for development
- [ ] All UI text in Romanian
- [ ] Cross-platform: Windows 11 Pro (production) + macOS (development)
- [ ] Process management: start/stop detector from web UI
- [ ] System status display: FPS, active tracks, webhook status, uptime
- [ ] Computer must not turn off or sleep while system is active

### Out of Scope

- Modifying the detection algorithm (YOLOv8 + BoT-SORT + dual-zone scoring) — works perfectly
- Mobile app — desktop kiosk only
- Multi-camera support — single camera per instance
- Cloud deployment — runs on local mini PC
- User authentication for the web UI — single operator, local network only

## Context

**Existing system:**
- Python 3.11+ codebase with FastAPI (port 8080), YOLOv8, OpenCV, BoT-SORT
- Detection pipeline: VideoStream → PersonTracker → EntryAnalyzer → WebhookSender → Dashboard
- Current dashboard: MJPEG stream + WebSocket state updates + calibration UI
- Current controller: VLC RC socket interface (unreliable), Flask (port 5050), sounddevice + Faster Whisper
- Webhook flow: detector emits `person_entered` → controller receives on port 5050 → plays instructional video

**What's changing:**
- VLC-based video playback → HTML5 video in browser
- Flask controller webhook listener → FastAPI integrated endpoint
- sounddevice mic recording → Web Audio API in browser → backend transcription
- Separate FastAPI dashboard → Vite frontend consuming FastAPI API
- Two separate processes → unified system managed from web UI

**Production environment:**
- Windows 11 Pro mini PC at clinic reception
- USB webcam pointed at entrance
- Local network, no internet required for operation
- Operator uses keyboard shortcuts, not mouse primarily

## Constraints

- **Stack**: Vite + vanilla JS/lightweight framework for frontend — must be extremely lightweight
- **Backend**: Extend existing FastAPI, don't rebuild — preserve all detection logic
- **Platform**: Must work on both Windows 11 Pro and macOS without modification
- **Performance**: Detection runs at 15 FPS on 1280x720 — frontend must not degrade this
- **Language**: Romanian UI only (no i18n needed, hardcode Romanian strings)
- **Network**: Local only, no external dependencies at runtime
- **Process**: Detector Python process must be manageable (start/stop) from the web UI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Vite for frontend | Lightweight, fast builds, no framework overhead | — Pending |
| HTML5 video replaces VLC | Browser-native, no external process, more reliable | — Pending |
| Web Audio API for mic | Works in browser kiosk mode, sends chunks to backend | — Pending |
| Extend FastAPI backend | Preserve working detection, add process mgmt + transcription | — Pending |
| Kiosk mode via browser flags | Chrome --kiosk or similar, cross-platform | — Pending |
| Sleep prevention via OS commands | caffeinate (macOS) / powercfg (Windows), toggled by backend | — Pending |

---
*Last updated: 2026-03-05 after initialization*
