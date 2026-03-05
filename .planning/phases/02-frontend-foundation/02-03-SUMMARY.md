---
phase: 02-frontend-foundation
plan: 03
subsystem: ui
tags: [keyboard-shortcuts, i18n-ro, api-wrappers, kiosk-controls]

# Dependency graph
requires:
  - phase: 02-frontend-foundation/01
    provides: "Vite scaffold, MJPEG feed, WebSocket client, app state"
  - phase: 02-frontend-foundation/02
    provides: "UI rendering functions (updateStatusPanel, updateEntryLog, updateWsBadge)"
provides:
  - "Keyboard shortcut system (registerShortcut + initShortcuts)"
  - "REST API wrappers for all backend endpoints"
  - "Centralized Romanian UI string constants (RO object)"
  - "F2/F3/F4/Escape operator keyboard controls"
affects: [03-kiosk-state-machine, 04-video-audio]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "event.code keydown listener with preventDefault for browser key suppression"
    - "Centralized i18n constants object (RO) for all user-facing text"
    - "Generic typed post/get fetch helpers for API calls"

key-files:
  created:
    - frontend/src/api.ts
    - frontend/src/shortcuts.ts
    - frontend/src/ro.ts
  modified:
    - frontend/src/main.ts
    - frontend/src/ui.ts
    - frontend/index.html

key-decisions:
  - "event.code (not event.key) for physical key position matching regardless of layout"
  - "canvas.style.opacity for F3 overlay toggle -- preserves MJPEG fetch connection (display:none would break it)"
  - "Centralized RO constants object instead of per-file strings for maintainability"
  - "Generic typed post/get helpers in api.ts reduce boilerplate for all 6 endpoints"

patterns-established:
  - "Keyboard shortcuts: registerShortcut(code, handler) + initShortcuts() pattern"
  - "API wrappers: typed generic post<T>/get<T> helpers with error logging"
  - "Romanian text: import { RO } from './ro.ts' for all user-facing strings"

requirements-completed: [FEED-02, KEYS-01, KEYS-02, KEYS-03, KEYS-04, KEYS-05, KIOSK-03, KIOSK-06]

# Metrics
duration: 4min
completed: 2026-03-05
---

# Phase 2 Plan 3: Keyboard Shortcuts and Romanian UI Summary

**F2/F3/F4/Escape keyboard shortcuts bound to API endpoints with centralized Romanian string constants**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T10:00:25Z
- **Completed:** 2026-03-05T10:04:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- All 4 keyboard shortcuts (F2 start/stop, F3 overlay toggle, F4 test webhook, Escape emergency stop) registered and functional
- Typed REST API wrappers for all 6 backend endpoints (process start/stop/status, test-webhook, wake-lock activate/release)
- All UI text centralized in Romanian constants file (RO object with 30+ string constants)
- ui.ts inline strings replaced with RO.RUNNING, RO.STOPPED, RO.CONNECTED, etc.

## Task Commits

Each task was committed atomically:

1. **Task 1: API wrappers and keyboard shortcut bindings** - `f570069` (feat)
2. **Task 2: Romanian UI strings and DOM text replacement** - `826907d` (feat)
3. **Merge fix: Re-add shortcuts after parallel plan overwrite** - `739f2cc` (fix)

## Files Created/Modified
- `frontend/src/api.ts` - Typed REST API wrappers (post/get helpers, 6 endpoint functions)
- `frontend/src/shortcuts.ts` - Keyboard shortcut registry with event.code keydown listener
- `frontend/src/ro.ts` - Centralized Romanian UI string constants (30+ entries)
- `frontend/src/main.ts` - Registers F2/F3/F4/Escape shortcuts, imports api + shortcuts modules
- `frontend/src/ui.ts` - Replaced inline Romanian strings with RO constant references
- `frontend/index.html` - Full Romanian title, Blocare ecran label, shortcuts hint text

## Decisions Made
- Used event.code (not event.key) for physical key position matching regardless of keyboard layout
- F3 overlay toggle uses canvas.style.opacity (not display:none) to preserve MJPEG fetch-to-canvas connection
- Generic typed post<T>/get<T> helpers in api.ts reduce boilerplate across all 6 endpoint wrappers
- Centralized RO object pattern for Romanian strings instead of per-file inline constants

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Parallel plan 02-02 overwrote main.ts losing shortcut code**
- **Found during:** Task 2 (Romanian strings task)
- **Issue:** Plan 02-02 running in parallel wrote a new version of main.ts that included UI wiring but dropped all shortcut imports and registrations from Task 1
- **Fix:** Re-applied shortcut imports (api.ts, shortcuts.ts, appState) and all 4 registerShortcut calls additively to the 02-02 version of main.ts
- **Files modified:** frontend/src/main.ts
- **Verification:** TypeScript compiles, build succeeds, both UI rendering and shortcuts present
- **Committed in:** 739f2cc

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary merge resolution for parallel execution. No scope creep.

## Issues Encountered
- Parallel plan 02-02 modified main.ts concurrently, requiring a merge commit to re-add shortcut code. This was expected given the plan's warning about overlap on main.ts and index.html.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Keyboard shortcuts ready for kiosk state machine integration (Phase 3)
- API wrappers ready for any future backend calls
- Romanian string constants available for all future UI components
- All Phase 2 frontend foundation plans complete

## Self-Check: PASSED

- frontend/src/api.ts: FOUND
- frontend/src/shortcuts.ts: FOUND
- frontend/src/ro.ts: FOUND
- Commit f570069: FOUND
- Commit 826907d: FOUND
- Commit 739f2cc: FOUND

---
*Phase: 02-frontend-foundation*
*Completed: 2026-03-05*
