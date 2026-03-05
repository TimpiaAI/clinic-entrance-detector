---
phase: 05-workflow-state-machine
plan: 02
subsystem: frontend
tags: [system-control, crash-detection, health-monitoring, auto-start, lifecycle, typescript]

# Dependency graph
requires:
  - phase: 05-workflow-state-machine
    provides: workflow.ts state machine with startWorkflow/stopWorkflow/onPersonEntered
  - phase: 04-audio-pipeline
    provides: initAudio() and isMicReady() for deferred mic initialization
  - phase: 02-frontend-foundation
    provides: api.ts wrappers, state.ts WebSocket state, shortcuts.ts key handling
provides:
  - system-control.ts with startSystem, stopSystem, emergencyStop, toggleSystem, autoStart
  - Health monitoring via 5s polling + WebSocket state diffing for crash detection
  - Crash alert overlay with Romanian text and Restart button
  - Start/Stop button in sidebar mirroring F2 behavior
  - Auto-start detection pipeline on page load (CTRL-03)
  - checkForPersonEnteredWorkflow event log diffing in workflow.ts
affects: [06-kiosk-hardening, frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [system-lifecycle-orchestration, dual-crash-detection, fire-and-forget-emergency-stop]

key-files:
  created:
    - frontend/src/system-control.ts
  modified:
    - frontend/src/main.ts
    - frontend/src/ui.ts
    - frontend/src/ro.ts
    - frontend/src/style.css
    - frontend/src/workflow.ts
    - frontend/index.html

key-decisions:
  - "autoStart() starts detector + wake-lock + health monitor but NOT workflow -- workflow requires F2 press"
  - "Dual crash detection: 5s HTTP polling + WebSocket state diffing for fastest possible detection"
  - "emergencyStop() uses fire-and-forget API calls (no await) for immediate UI response"
  - "checkForPersonEnteredWorkflow added to workflow.ts with timestamp-diffing pattern from video.ts"
  - "System toggle button positioned fixed in sidebar area with z-index 31 above panels"

patterns-established:
  - "System lifecycle: startSystem/stopSystem orchestrate all subsystems in defined order"
  - "Dual crash detection: polling + WebSocket diffing catch crashes within 2-5 seconds"
  - "Emergency stop pattern: synchronous workflow abort, fire-and-forget API cleanup"
  - "Person-entered routing: workflow handles when active, Phase 3 fallback when stopped"

requirements-completed: [CTRL-01, CTRL-02, CTRL-03, CTRL-04, CTRL-05]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 5 Plan 2: System Control Summary

**System lifecycle orchestration with F2 start/stop toggle, Escape emergency stop, auto-start on page load, 5s health polling, and WebSocket crash detection with Romanian alert**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T14:52:28Z
- **Completed:** 2026-03-05T14:56:01Z
- **Tasks:** 2
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- Created system-control.ts (238 lines) orchestrating full system lifecycle: detector, wake-lock, audio, workflow, health monitoring
- Rewired main.ts to use toggleSystem() for F2, emergencyStop() for Escape, autoStart() on page load
- Added crash detection via dual approach: 5s HTTP polling and WebSocket state diffing
- Added crash alert overlay with Romanian text and one-click Restart button
- Added system toggle button in sidebar for mouse-based start/stop
- Added checkForPersonEnteredWorkflow to workflow.ts for event log diffing integration

## Task Commits

Each task was committed atomically:

1. **Task 1: system-control.ts module, crash alert UI, and DOM elements** - `111fd3d` (feat)
2. **Task 2: Rewire main.ts with workflow, system control, and auto-start** - `e1f4341` (feat)

## Files Created/Modified

- `frontend/src/system-control.ts` - System lifecycle: start/stop/emergency/autoStart/health/crash detection (238 lines)
- `frontend/src/main.ts` - Rewired entry point importing system-control and workflow (101 lines)
- `frontend/src/ui.ts` - Added showCrashAlert, hideCrashAlert, updateSystemButton functions
- `frontend/src/ro.ts` - Romanian strings for system control (SYSTEM_START, CRASH_ALERT, etc.)
- `frontend/src/style.css` - Crash alert overlay and system toggle button styles
- `frontend/src/workflow.ts` - Added checkForPersonEnteredWorkflow for event log diffing
- `frontend/index.html` - Added crash-alert DOM element and system-toggle-btn

## Decisions Made

- autoStart() activates detector + wake-lock + health monitor on page load, but NOT the workflow -- operator must press F2 to start patient interaction cycle (CTRL-03 says "detection pipeline" not "workflow")
- Dual crash detection strategy: 5s polling catches HTTP-level issues, WebSocket diffing catches state transitions within ~0.5s
- emergencyStop() is synchronous for immediate UI response -- API calls are fire-and-forget (no await) since the user expects instant abort
- Person-entered events are routed based on workflow state: workflow handles when active, Phase 3 linear sequence when workflow is stopped (preserves F4 testing)
- checkForPersonEnteredWorkflow added to workflow.ts rather than main.ts to keep event log diffing co-located with onPersonEntered()

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added checkForPersonEnteredWorkflow to workflow.ts**
- **Found during:** Task 2
- **Issue:** Plan references `checkForPersonEnteredWorkflow` import from workflow.ts but the function did not exist -- Plan 01 did not include it
- **Fix:** Added the function with timestamp-diffing pattern (mirroring video.ts) and added EventLogEntry to the import
- **Files modified:** frontend/src/workflow.ts
- **Verification:** TypeScript compiles, build succeeds
- **Committed in:** e1f4341 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for main.ts integration. No scope creep.

## Issues Encountered

None - all TypeScript compilation and builds succeeded on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 is complete: workflow state machine (Plan 01) + system control (Plan 02) fully integrated
- Phase 6 (Kiosk Hardening) can begin: Chrome kiosk launch script, two-layer sleep prevention, Windows 11 validation
- All CTRL requirements (01-05) and WKFL requirements (01-05) are satisfied

## Self-Check: PASSED

All 7 source files verified. Both task commits (111fd3d, e1f4341) verified in git log.

---
*Phase: 05-workflow-state-machine*
*Completed: 2026-03-05*
