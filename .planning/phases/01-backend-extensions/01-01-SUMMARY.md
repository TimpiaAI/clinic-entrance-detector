---
phase: 01-backend-extensions
plan: 01
subsystem: api
tags: [fastapi, subprocess, psutil, process-management]

# Dependency graph
requires:
  - phase: none
    provides: "First plan in first phase -- no prior dependencies"
provides:
  - "POST /api/process/start endpoint to start detector subprocess"
  - "POST /api/process/stop endpoint with psutil tree kill"
  - "GET /api/process/status endpoint for detector state"
  - "api/process_manager.py module with router, start_detector, stop_detector, detector_status exports"
affects: [02-frontend-foundation, 05-workflow-state-machine]

# Tech tracking
tech-stack:
  added: [pytest]
  patterns: [APIRouter-module-in-app-factory, module-level-singleton-process, psutil-tree-kill]

key-files:
  created: [api/__init__.py, api/process_manager.py, tests/test_process_manager.py]
  modified: [dashboard/web.py]

key-decisions:
  - "Followed RESEARCH.md Pattern 2 exactly: module-level _detector_proc singleton with psutil tree kill"
  - "Installed pytest as test framework (was missing from venv)"

patterns-established:
  - "APIRouter modules under api/ included via app.include_router() in create_dashboard_app()"
  - "Module-level subprocess singleton for process lifecycle management"
  - "psutil tree kill: enumerate children(recursive=True), terminate all, wait_procs(timeout=5), force-kill survivors"

requirements-completed: [BACK-02, BACK-03, BACK-04]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 1 Plan 1: Process Manager Summary

**Subprocess start/stop/status API with psutil tree kill for reliable cross-platform detector lifecycle management**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T09:16:56Z
- **Completed:** 2026-03-05T09:19:46Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Process manager module with start/stop/status functions and FastAPI APIRouter
- psutil tree kill pattern ensures no orphan processes hold the camera after stop
- 9 unit tests with mocked subprocess/psutil covering all behavior cases
- Router integrated into existing create_dashboard_app() factory cleanly

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Failing tests for process manager** - `2a08857` (test)
2. **Task 1 (TDD GREEN): Process manager implementation** - `61bc66c` (feat)
3. **Task 2: Integrate process_manager router into dashboard app** - `e5662fc` (feat)

_Note: Task 1 followed TDD with RED (failing tests) then GREEN (implementation) commits._

## Files Created/Modified
- `api/__init__.py` - Package marker for new api module
- `api/process_manager.py` - Process management functions (start_detector, stop_detector, detector_status) and APIRouter with POST /start, POST /stop, GET /status
- `tests/test_process_manager.py` - 9 unit tests with mocked subprocess.Popen and psutil.Process
- `dashboard/web.py` - Added import and include_router for process_router

## Decisions Made
- Followed RESEARCH.md Pattern 2 exactly -- no deviations from the recommended implementation
- Installed pytest (was not in venv) to enable TDD workflow

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing pytest dependency**
- **Found during:** Task 1 (TDD infrastructure check)
- **Issue:** pytest not installed in project .venv, blocking test execution
- **Fix:** Ran `pip install pytest` in .venv
- **Files modified:** None (venv-only change)
- **Verification:** pytest 9.0.2 installed, all tests collect and run
- **Committed in:** N/A (venv package install, not committed)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- pytest is a standard test dependency. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Process management endpoints are ready for frontend integration (Phase 2+)
- Router pattern established for remaining Phase 1 plans (transcribe, sleep_guard)
- api/ module structure ready for api/transcribe.py and api/sleep_guard.py

## Self-Check: PASSED

All files verified present, all commits verified in git log.

---
*Phase: 01-backend-extensions*
*Completed: 2026-03-05*
