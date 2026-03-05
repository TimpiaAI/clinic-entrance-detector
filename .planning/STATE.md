---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Completed 03-02-PLAN.md (WebSocket event trigger + marquee overlays)
last_updated: "2026-03-05T10:41:13.337Z"
last_activity: 2026-03-05 — Completed 03-02 WebSocket event trigger + marquee overlays
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** When activated, the system reliably detects clinic entries, plays instructional videos, and captures patient data — all from a single browser window that never lets the computer sleep.
**Current focus:** Phase 3 complete — ready for Phase 4

## Current Position

Phase: 3 of 6 (Video Overlay) -- COMPLETE
Plan: 2 of 2 in current phase
Status: Phase Complete
Last activity: 2026-03-05 — Completed 03-02 WebSocket event trigger + marquee overlays

Progress: [██████████] 100% (Phase 3 complete, 8/8 plans done)

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 3min | 2 tasks | 4 files |
| Phase 01 P02 | 4min | 2 tasks | 5 files |
| Phase 01 P03 | 4min | 3 tasks | 6 files |
| Phase 02 P01 | 4min | 2 tasks | 11 files |
| Phase 02 P03 | 4min | 2 tasks | 6 files |
| Phase 02 P02 | 5min | 2 tasks | 5 files |
| Phase 03 P01 | 2min | 2 tasks | 5 files |
| Phase 03 P02 | 2min | 1 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Vite + vanilla TypeScript frontend — zero runtime overhead for single-screen kiosk state machine
- [Init]: HTML5 video replaces VLC — browser-native, no external process, more reliable
- [Init]: Extend FastAPI backend — preserve working detection pipeline, add process mgmt + transcription
- [Init]: Fetch-to-canvas for MJPEG (not img tag) — mandatory from day one to prevent 24/7 memory leak
- [Phase 01]: Followed RESEARCH.md Pattern 2 exactly: module-level _detector_proc singleton with psutil tree kill
- [Phase 01]: Installed pytest as test framework (was missing from venv)
- [Phase 01]: Word boundaries for short at/et/ad regex patterns prevent false matches in Romanian words
- [Phase 01]: Email extraction uses rfind('@') + last token for mixed-text robustness (improved over controller.py)
- [Phase 01]: Whisper import deferred inside get_model() to allow tests without faster-whisper loaded
- [Phase 01]: wakepy keep.presenting() entered/exited programmatically for on-demand sleep prevention
- [Phase 01]: Custom video endpoint with Range parsing (not StaticFiles) -- Chrome requires 206 for seeking
- [Phase 01]: ALLOWED_VIDEOS whitelist prevents arbitrary file access via video endpoint
- [Phase 01]: StaticFiles mount conditional on frontend_dist/ existence -- activates after Phase 2 build
- [Phase 01]: detector_running and wake_lock_active sourced from module functions in snapshot(), not cached
- [Phase 02]: fetch-to-canvas with URL.revokeObjectURL for MJPEG -- mandatory for 24/7 kiosk memory safety
- [Phase 02]: ws:// protocol auto-detection in main.ts for HTTPS compatibility in production
- [Phase 02]: setOnStateUpdate setter function instead of direct export assignment -- works with verbatimModuleSyntax
- [Phase 02]: Added frontend_dist/ to root .gitignore -- build artifact should not be committed
- [Phase 02]: event.code (not event.key) for physical key position matching regardless of keyboard layout
- [Phase 02]: canvas.style.opacity for F3 overlay toggle preserves MJPEG fetch connection (display:none would break it)
- [Phase 02]: Centralized RO constants object for Romanian UI strings instead of per-file inline text
- [Phase 02]: Event log thumbnail at 320px/quality 50 separate from webhook 640/70 to keep WebSocket payload reasonable
- [Phase 02]: Incremental entry log DOM updates via lastEventCount comparison instead of full table rebuild
- [Phase 03]: Single video element reuse with src swap -- avoids Chromium memory leak (crbug.com/41462045)
- [Phase 03]: onended event-driven sequence transitions -- no timers, reliable and drift-free
- [Phase 03]: opacity:0 for hiding video (not display:none) -- preserves element in render tree, prevents Chrome buffer release
- [Phase 03]: z-index spacing 1/10/20/30 -- provides insertion room between stacking layers
- [Phase 03]: muted attribute on video element ensures autoplay before user gesture; F2 keypress unmutes
- [Phase 03]: Timestamp comparison for person_entered dedup -- naturally handles WebSocket reconnects without extra logic
- [Phase 03]: VIDEO_LABELS Record mapping from filename to RO constant -- extensible if sequence changes

### Pending Todos

None yet.

### Blockers/Concerns

- [Pre-Phase 1]: ffmpeg must be on PATH on Windows 11 mini PC — verify before Phase 1 testing (/api/transcribe depends on it)
- [Pre-Phase 2]: Node.js 20.19+ or 22.12+ required for Vite 7 — check clinic mini PC before starting Phase 2
- [Pre-Phase 4]: Whisper model latency on clinic mini PC unknown — benchmark medium+int8 on actual hardware; downgrade to small if >30s
- [Pre-Phase 4]: Chrome kiosk getUserMedia permission flow needs validation — may require explicit operator gesture on first kiosk profile boot

## Session Continuity

Last session: 2026-03-05T10:37:24.980Z
Stopped at: Completed 03-02-PLAN.md (WebSocket event trigger + marquee overlays)
Resume file: None
