---
phase: 04-audio-pipeline
plan: 01
subsystem: audio
tags: [mediarecorder, webm, opus, whisper, getUserMedia, AudioContext, transcription]

# Dependency graph
requires:
  - phase: 02-frontend-foundation
    provides: api.ts REST wrappers, types.ts interfaces, main.ts shortcut handlers
  - phase: 01-backend-core
    provides: /api/transcribe endpoint with Faster Whisper
provides:
  - audio.ts module with mic capture and stop-and-collect MediaRecorder pattern
  - apiTranscribe FormData POST wrapper for /api/transcribe
  - TranscribeResult interface for typed transcription responses
  - initial_prompt parameter on backend transcription endpoint
  - Mic initialization wired into F2 user gesture handler
  - Romanian audio/recording UI strings
affects: [04-02-audio-pipeline, 05-workflow]

# Tech tracking
tech-stack:
  added: [MediaRecorder API, AudioContext API, getUserMedia]
  patterns: [stop-and-collect recording, user-gesture AudioContext creation, FormData multipart upload]

key-files:
  created: [frontend/src/audio.ts]
  modified: [frontend/src/api.ts, frontend/src/types.ts, frontend/src/main.ts, frontend/src/ro.ts, api/transcribe.py]

key-decisions:
  - "audio/webm;codecs=opus preferred MIME with fallback to audio/webm for browser compat"
  - "Test stream acquired and immediately released in initAudio -- actual recording gets fresh stream"
  - "Mic denial is non-blocking: detector still starts, audio fails gracefully when called later"
  - "Backend kwargs dict pattern for optional initial_prompt preserves backward compatibility"

patterns-established:
  - "User-gesture-gated initialization: AudioContext and mic permission requested inside F2 keydown handler"
  - "Stop-and-collect MediaRecorder: start with no timeslice, stop after duration, collect single blob"
  - "Track release after every recording: stream.getTracks().forEach(t => t.stop()) in onstop handler"
  - "FormData POST without Content-Type header (browser sets multipart boundary automatically)"

requirements-completed: [STT-01, STT-02, STT-03, STT-04, STT-06]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 4 Plan 1: Audio Capture Pipeline Summary

**Browser mic capture with MediaRecorder stop-and-collect pattern, apiTranscribe FormData wrapper, and initial_prompt on backend Whisper endpoint**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T13:23:23Z
- **Completed:** 2026-03-05T13:26:24Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created audio.ts module with full mic lifecycle: checkMicAvailability, initAudio, isMicReady, recordAndTranscribe
- Added apiTranscribe wrapper using FormData POST (no Content-Type header -- browser sets multipart boundary)
- Extended /api/transcribe with optional initial_prompt Form parameter for improved CNP/email Whisper accuracy
- Wired mic initialization into F2 handler inside user gesture context (AudioContext + getUserMedia)
- Added 10 Romanian audio strings for recording UI (Phase 5 will use these)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create audio.ts module and extend backend with initial_prompt** - `0bc2e73` (feat)
2. **Task 2: Wire mic initialization into F2 handler and add Romanian strings** - `6822f1a` (feat)

## Files Created/Modified
- `frontend/src/audio.ts` - Browser audio capture module with MediaRecorder stop-and-collect pattern (new, 126 lines)
- `frontend/src/api.ts` - Added apiTranscribe FormData POST wrapper and TranscribeResult import
- `frontend/src/types.ts` - Added TranscribeResult interface (text, cnp, email)
- `frontend/src/main.ts` - Wired initAudio()/isMicReady() into F2 shortcut handler
- `frontend/src/ro.ts` - Added 10 Romanian audio/recording strings to RO constants
- `api/transcribe.py` - Added optional initial_prompt Form parameter, kwargs dict for model.transcribe()

## Decisions Made
- audio/webm;codecs=opus as preferred MIME type with fallback to audio/webm (opus is the most efficient browser audio codec)
- initAudio() requests a test getUserMedia stream then immediately releases it -- recordAndTranscribe() acquires its own fresh stream each time (cleaner lifecycle, avoids holding long-lived streams)
- Mic permission denial is non-blocking in F2 handler -- detector can still start, audio will fail gracefully when Phase 5 workflow tries to record
- Backend uses kwargs dict pattern for optional initial_prompt instead of two code paths -- cleaner and backward compatible

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Backend pytest tests could not run due to missing FastAPI in development venv (pre-existing environment issue on macOS, production runs on Windows mini PC). Change is backward compatible by design: initial_prompt defaults to Form(None).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- audio.ts exports are ready for Phase 4 Plan 2 (audio playback/TTS) and Phase 5 (workflow state machine)
- recordAndTranscribe() accepts initialPrompt parameter for Phase 5 to pass CNP/email-specific prompts
- All 10 Romanian strings are available for Phase 5 UI feedback during recording/processing/confirmation

## Self-Check: PASSED

All 7 files verified present. Both task commits (0bc2e73, 6822f1a) confirmed in git log.

---
*Phase: 04-audio-pipeline*
*Completed: 2026-03-05*
