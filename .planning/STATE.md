# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** When activated, the system reliably detects clinic entries, plays instructional videos, and captures patient data — all from a single browser window that never lets the computer sleep.
**Current focus:** Phase 1 — Backend Extensions

## Current Position

Phase: 1 of 6 (Backend Extensions)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-03-05 — Roadmap created, phases derived from requirements

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Vite + vanilla TypeScript frontend — zero runtime overhead for single-screen kiosk state machine
- [Init]: HTML5 video replaces VLC — browser-native, no external process, more reliable
- [Init]: Extend FastAPI backend — preserve working detection pipeline, add process mgmt + transcription
- [Init]: Fetch-to-canvas for MJPEG (not img tag) — mandatory from day one to prevent 24/7 memory leak

### Pending Todos

None yet.

### Blockers/Concerns

- [Pre-Phase 1]: ffmpeg must be on PATH on Windows 11 mini PC — verify before Phase 1 testing (/api/transcribe depends on it)
- [Pre-Phase 2]: Node.js 20.19+ or 22.12+ required for Vite 7 — check clinic mini PC before starting Phase 2
- [Pre-Phase 4]: Whisper model latency on clinic mini PC unknown — benchmark medium+int8 on actual hardware; downgrade to small if >30s
- [Pre-Phase 4]: Chrome kiosk getUserMedia permission flow needs validation — may require explicit operator gesture on first kiosk profile boot

## Session Continuity

Last session: 2026-03-05
Stopped at: Roadmap created — 47 requirements mapped to 6 phases; ready to plan Phase 1
Resume file: None
