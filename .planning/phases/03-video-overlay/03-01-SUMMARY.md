---
phase: 03-video-overlay
plan: 01
subsystem: ui
tags: [html5-video, css-z-index, video-overlay, src-swap, state-machine]

# Dependency graph
requires:
  - phase: 02-frontend-foundation
    provides: index.html shell with canvas#feed, style.css dark theme, main.ts entry point
provides:
  - Video overlay DOM elements (video#video-overlay, div#text-overlay)
  - CSS z-index stacking layout (feed < video < text < sidebar)
  - video.ts module with idle loop, instructional sequence, and state machine
  - Romanian video string constants in ro.ts
affects: [03-video-overlay/03-02, 04-voice-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [single-element-src-swap, onended-event-transitions, opacity-visibility-pattern]

key-files:
  created: [frontend/src/video.ts]
  modified: [frontend/index.html, frontend/src/style.css, frontend/src/main.ts, frontend/src/ro.ts]

key-decisions:
  - "Single video element reuse with src swap -- avoids Chromium memory leak (crbug.com/41462045)"
  - "onended event-driven sequence transitions -- no timers, no polling"
  - "opacity:0 for hiding instead of display:none -- preserves element in render tree, prevents Chrome buffer release"
  - "z-index spacing 1/10/20/30 -- provides insertion room between layers"
  - "muted attribute on video element -- ensures autoplay works before user gesture"

patterns-established:
  - "Single-element src-swap: Reuse one video element, change src, call load(), play()"
  - "Event-driven transitions: addEventListener('ended') drives sequence progression"
  - "Opacity visibility: opacity:0 instead of display:none for persistent media elements"

requirements-completed: [VCTL-01, VCTL-03, VCTL-05]

# Metrics
duration: 2min
completed: 2026-03-05
---

# Phase 3 Plan 01: Video Overlay Infrastructure Summary

**HTML5 video overlay with z-index stacking, single-element src-swap idle loop on video1.mp4, and onended-driven instructional sequence matching controller.py order**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T10:29:20Z
- **Completed:** 2026-03-05T10:31:34Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Video and text overlay DOM elements added to index.html with correct stacking order
- CSS z-index layout: feed(1) < video(10) < text-overlay(20) < sidebar(30) with responsive overrides
- video.ts module with 6 exported functions: initVideo, startIdleLoop, startInstructionSequence, hideVideo, onUserGesture, getVideoState
- Idle loop plays video1.mp4 with loop=true; instructional sequence plays video2,3,6,7,8,4,5 in exact controller.py order
- 10 Romanian video string constants added to ro.ts for Plan 03-02 marquee text

## Task Commits

Each task was committed atomically:

1. **Task 1: Add video/text overlay DOM elements and CSS z-index stacking** - `b214e33` (feat)
2. **Task 2: Create video.ts module with idle loop and instructional sequence** - `74ded54` (feat)

## Files Created/Modified
- `frontend/src/video.ts` - Video playback module: idle loop, instructional sequence state machine, user gesture unmute
- `frontend/index.html` - Added video#video-overlay and div#text-overlay elements inside #app
- `frontend/src/style.css` - z-index stacking (1/10/20/30), video/text overlay positioning, marquee animation
- `frontend/src/main.ts` - Import and wire initVideo(), startIdleLoop(), onUserGesture() from video.ts
- `frontend/src/ro.ts` - 10 Romanian video-related string constants (VIDEO_IDLE, VIDEO_GREETING, etc.)

## Decisions Made
- Single video element reuse with src swap avoids Chromium memory leak (crbug.com/41462045) -- never create/destroy video elements
- onended event-driven sequence transitions instead of timers -- reliable, no drift, no race conditions
- opacity:0 hiding instead of display:none -- preserves element in render tree, prevents Chrome from releasing buffered data
- z-index spacing 1/10/20/30 -- provides insertion room between layers for future overlays
- muted attribute on video element ensures autoplay works before user gesture; F2 keypress unmutes via onUserGesture()

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Video overlay infrastructure complete, ready for Plan 03-02 to wire WebSocket person_entered events and add marquee text
- video.ts exports startInstructionSequence() which Plan 03-02 will call on person_entered
- text overlay DOM and marquee CSS ready for Plan 03-02 to populate with RO strings

## Self-Check: PASSED

- [x] frontend/src/video.ts exists
- [x] 03-01-SUMMARY.md exists
- [x] Commit b214e33 found
- [x] Commit 74ded54 found

---
*Phase: 03-video-overlay*
*Completed: 2026-03-05*
