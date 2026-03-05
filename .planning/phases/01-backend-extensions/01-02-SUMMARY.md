---
phase: 01-backend-extensions
plan: 02
subsystem: api
tags: [faster-whisper, transcription, cnp, email, regex, fastapi, tdd]

# Dependency graph
requires: []
provides:
  - "POST /api/transcribe endpoint accepting audio and returning {text, cnp, email}"
  - "extract_cnp() pure function for Romanian CNP extraction from speech"
  - "extract_email() pure function handling Romanian speech artifacts (arond, punct, etc.)"
  - "Lazy-loaded Whisper model singleton via get_model()"
affects: [04-browser-workflow]

# Tech tracking
tech-stack:
  added: [faster-whisper 1.2.1, ctranslate2, PyAV, onnxruntime]
  patterns: [lazy-loaded-singleton, tdd-red-green, regex-speech-normalization]

key-files:
  created: [api/transcribe.py, tests/test_transcribe.py, api/__init__.py]
  modified: [dashboard/web.py, .env]

key-decisions:
  - "Used word boundaries for short at/et/ad patterns to prevent false matches inside Romanian words"
  - "Email extraction uses rfind('@') and takes last token before @ to handle mixed text (not just pure email input)"
  - "Whisper import deferred inside get_model() to avoid import-time dependency on faster-whisper for tests"

patterns-established:
  - "Lazy singleton: module-level _model = None, get_model() checks and creates on first call"
  - "Speech normalization: two-pass regex (domain dots first, then @ variants) for Romanian transcription"
  - "TDD for pure extraction functions: tests written first, implementation follows"

requirements-completed: [BACK-05]

# Metrics
duration: 4min
completed: 2026-03-05
---

# Phase 1 Plan 2: Transcription Endpoint Summary

**POST /api/transcribe with Faster Whisper lazy-load, CNP 13-digit extraction, and Romanian speech email normalization (arond/@, punct/.)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T09:17:01Z
- **Completed:** 2026-03-05T09:21:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- POST /api/transcribe endpoint accepts audio files (WebM/WAV), transcribes with Faster Whisper, returns structured {text, cnp, email}
- CNP extraction handles 13+ digits (full CNP), 10-12 digits (partial for confirmation), and <10 digits (None)
- Email extraction ports and improves Romanian speech artifact handling from controller.py (arond/arong/arung/at/et/ad -> @, punct/dot -> .)
- Whisper model lazy-loaded on first request (not at import time) via module-level singleton
- 16 unit tests covering all extraction edge cases and endpoint behavior

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for CNP/email extraction and endpoint** - `ed549dd` (test)
2. **Task 1 (GREEN): Implement transcribe endpoint, extract_cnp, extract_email** - `30f9fc9` (feat)
3. **Task 2: Install faster-whisper and integrate transcribe router** - `4e995e5` (feat)

## Files Created/Modified
- `api/__init__.py` - Package init for new api/ module directory
- `api/transcribe.py` - Transcription endpoint with Whisper lazy-load, CNP/email extraction (103 lines)
- `tests/test_transcribe.py` - 16 unit tests for extraction functions and endpoint (178 lines)
- `dashboard/web.py` - Added transcribe_router import and include_router call
- `.env` - Added WHISPER_MODEL and WHISPER_COMPUTE_TYPE env vars

## Decisions Made
- Used word boundaries (\b) for short at/et/ad regex patterns to prevent false matches inside Romanian words like "adresa" or "este" (found during GREEN phase when tests failed)
- Email extraction redesigned to use rfind('@') and take only the last whitespace token before '@', enabling extraction from mixed text (not just pure email dictation as in controller.py)
- Whisper import deferred inside get_model() function body (not at module level) so tests can run without faster-whisper installed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed false-positive @ matches in Romanian words**
- **Found during:** Task 1 (GREEN phase, tests failing)
- **Issue:** Short patterns "at", "et", "ad" matched inside common Romanian words ("adresa" -> "@resa", "este" -> "es@")
- **Fix:** Split the regex into two passes: long patterns (arond, arong, etc.) without boundaries, short patterns (at, et, ad) with word boundaries (\b)
- **Files modified:** api/transcribe.py
- **Verification:** All 16 tests pass
- **Committed in:** 30f9fc9

**2. [Rule 1 - Bug] Fixed email extraction from mixed transcription text**
- **Found during:** Task 1 (GREEN phase, endpoint test failing)
- **Issue:** When transcription contains both CNP digits and email in same text, the local part captured all preceding text before "@"
- **Fix:** Changed to use rfind('@') and take only the last whitespace-delimited token before '@' as the local part
- **Files modified:** api/transcribe.py
- **Verification:** Endpoint test with mixed CNP+email text passes
- **Committed in:** 30f9fc9

---

**Total deviations:** 2 auto-fixed (2 bugs in regex matching)
**Impact on plan:** Both auto-fixes necessary for correctness. Improved robustness vs. controller.py original which assumed single-purpose input. No scope creep.

## Issues Encountered
None beyond the regex issues documented above as deviations.

## User Setup Required
None - no external service configuration required. WHISPER_MODEL and WHISPER_COMPUTE_TYPE added to .env with defaults.

## Next Phase Readiness
- Transcription endpoint ready for browser integration in Phase 4
- The api/ directory structure is established for future endpoints (sleep_guard, etc.)
- faster-whisper installed and verified in .venv

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 01-backend-extensions*
*Completed: 2026-03-05*
