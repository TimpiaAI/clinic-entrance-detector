---
phase: 05-workflow-state-machine
plan: 01
subsystem: frontend, api
tags: [state-machine, workflow, video, audio, transcription, fastapi, typescript]

# Dependency graph
requires:
  - phase: 01-backend-api
    provides: process_manager.py subprocess control, web.py DashboardState + WebSocket
  - phase: 03-video-overlay
    provides: video.ts playback primitives, idle loop, onended event wiring
  - phase: 04-audio-pipeline
    provides: audio.ts recordAndTranscribe, ui.ts transcription panel
provides:
  - workflow.ts state machine with 19 states and full patient interaction cycle
  - playSingleVideo() callback-based video API for workflow control
  - POST /trigger webhook relay from detector subprocess to DashboardState
  - POST /api/submit-patient endpoint for patient data logging
  - showConfirmationSummary() UI for final data review
  - WorkflowState and PatientData type definitions
  - --no-dashboard flag and WEBHOOK_URL env passed to detector subprocess
affects: [05-02-system-control, frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [explicit-state-machine, callback-based-video-control, recording-cancellation-flag]

key-files:
  created:
    - frontend/src/workflow.ts
  modified:
    - api/process_manager.py
    - dashboard/web.py
    - frontend/src/video.ts
    - frontend/src/types.ts
    - frontend/src/api.ts
    - frontend/src/ui.ts
    - frontend/src/ro.ts

key-decisions:
  - "Explicit state machine with switch/case dispatch -- no library needed for 19 linear states"
  - "playSingleVideo() with onEnded callback replaces linear instruction sequence for workflow control"
  - "Recording cancellation via flag pattern -- cannot truly abort MediaRecorder but results discarded on cancel"
  - "show_* states are transient -- immediately transition to next ask/confirm step after data is stored"
  - "Parent-dashboard mode: subprocess gets --no-dashboard + WEBHOOK_URL, parent relays via /trigger"
  - "Patient data submission logs to Python logger in v1 (no external target configured)"

patterns-established:
  - "Callback-based video: playSingleVideo(filename, onEnded) for individual video control by workflow"
  - "Recording cancellation: set recordingCancelled flag, check after Promise resolves, discard if cancelled"
  - "State timeout pattern: per-state configurable timeout clears data and returns to idle"
  - "Webhook relay: subprocess POSTs to parent /trigger, parent pushes to DashboardState for WebSocket broadcast"

requirements-completed: [WKFL-01, WKFL-02, WKFL-03, WKFL-04, WKFL-05]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 5 Plan 1: Workflow State Machine Summary

**Complete patient workflow state machine (19 states) with video-then-record orchestration, timeout handling, confirmation summary UI, and backend webhook relay from detector subprocess**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T14:44:16Z
- **Completed:** 2026-03-05T14:48:58Z
- **Tasks:** 2
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments

- Built workflow.ts (538 lines) with all 19 workflow states and transitions matching controller.py sequence exactly
- Added playSingleVideo() export to video.ts for callback-based individual video control
- Fixed process_manager.py to pass --no-dashboard and WEBHOOK_URL to detector subprocess
- Added POST /trigger endpoint to relay person_entered events from subprocess to WebSocket clients
- Added POST /api/submit-patient endpoint for patient data logging
- Added showConfirmationSummary() to ui.ts showing all 4 fields (name, question, CNP, email) before submission
- TypeScript compiles with zero errors; Vite build succeeds

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend webhook relay** - `161c5ea` (feat)
2. **Task 2: Workflow state machine, video single-play, types, confirmation UI** - `ad1f932` (feat)

## Files Created/Modified

- `frontend/src/workflow.ts` - Core state machine with 19 states, transitions, timeouts, recording orchestration
- `api/process_manager.py` - --no-dashboard flag and WEBHOOK_URL env var for subprocess
- `dashboard/web.py` - POST /trigger webhook relay + POST /api/submit-patient
- `frontend/src/video.ts` - playSingleVideo() export with onEnded callback
- `frontend/src/types.ts` - WorkflowState union type and PatientData interface
- `frontend/src/api.ts` - apiSubmitPatient() endpoint wrapper
- `frontend/src/ui.ts` - showConfirmationSummary() for final data review
- `frontend/src/ro.ts` - Romanian workflow strings (9 new constants)

## Decisions Made

- Used explicit switch/case state machine (no XState/library) -- 19 linear states don't justify library overhead
- playSingleVideo() with callback replaces startInstructionSequence() for workflow -- existing F4 test sequence preserved
- Recording cancellation via flag (not true abort) -- MediaRecorder cannot be externally cancelled; Promise result is simply discarded
- show_* states are transient pass-through -- they immediately transition to the next ask step (data already stored by confirm callback)
- Parent-dashboard architecture: subprocess runs headless, POSTs webhooks to parent /trigger, parent broadcasts via WebSocket
- v1 patient submission logs to Python logger -- no external webhook target configured yet

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Python venv psutil not importable from system Python -- verified via AST syntax parsing instead of full import (runtime dependency available on target)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Workflow state machine ready; Plan 05-02 (system control) will wire it into main.ts with F2 start/stop and Escape emergency stop
- onPersonEntered() exported from workflow.ts ready to replace checkForPersonEntered() in main.ts
- startWorkflow()/stopWorkflow() ready for F2/Escape integration

## Self-Check: PASSED

All 8 source files found. Both task commits (161c5ea, ad1f932) verified in git log. SUMMARY.md created.

---
*Phase: 05-workflow-state-machine*
*Completed: 2026-03-05*
