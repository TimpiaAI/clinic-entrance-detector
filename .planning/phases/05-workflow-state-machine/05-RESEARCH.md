# Phase 5: Workflow State Machine - Research

**Researched:** 2026-03-05
**Domain:** Frontend state machine orchestration, system control, process health monitoring, crash recovery
**Confidence:** HIGH

## Summary

Phase 5 wires together all four previously built subsystems (backend process management, frontend foundation, video overlay, audio pipeline) into a complete patient workflow state machine and system control layer. The core challenge is building a TypeScript state machine (`workflow.ts`) that orchestrates video playback pauses for recording, integrates transcription results with confirmation steps, handles timeouts for patient abandonment, and manages the full system lifecycle (start/stop/crash recovery).

The controller.py reference implementation reveals the exact workflow sequence: idle -> greeting (video2) -> ask name (video3) -> record -> show -> ask question (video6) -> record -> show -> ask CNP (video7) -> record -> show -> ask email (video8) -> record -> show -> farewell (video4) -> brief idle (video1 for 5s) -> final (video5) -> back to idle. Critically, recording happens AFTER specific question videos (video3, video6, video7, video8), not during them. During recording, idle video loops as background while the transcription panel shows.

The second major responsibility is system control: F2 starts the full system (detector + wake-lock + idle video + WebSocket), Escape stops everything, process health is polled every 5 seconds via `/api/process/status`, and crash recovery shows a "Restart" UI option. A critical architectural finding is that the process manager currently does NOT pass `--no-dashboard` when spawning main.py as a subprocess, meaning the subprocess starts its own dashboard server on port 8080. Phase 5 must either fix this (pass `--no-dashboard` + add a `/trigger` endpoint for webhook relay) or ensure the frontend connects to the subprocess's dashboard WebSocket.

**Primary recommendation:** Build workflow.ts as a pure state machine with explicit states, transitions, and timeout timers. Modify the process manager to pass `--no-dashboard` and add a `/trigger` webhook relay endpoint to the parent FastAPI process. Wire the system control layer into existing F2/Escape shortcuts.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WKFL-01 | Full patient workflow cycle: idle -> greeting -> ask_name -> record -> show -> ask_cnp -> record -> show -> ask_email -> record -> confirm -> submit -> farewell -> idle | controller.py workflow() exactly defines the sequence; video.ts INSTRUCTION_SEQUENCE already has the video order; audio.ts recordAndTranscribe already works; ui.ts transcription panel already exists |
| WKFL-02 | Each workflow state has a timeout that returns to idle if exceeded (patient abandonment) | controller.py has no timeout -- this is a new improvement; use setTimeout per state with configurable durations |
| WKFL-03 | Captured patient data is cleared on timeout or workflow completion | workflow.ts needs a PatientData object that is reset on idle transition |
| WKFL-04 | Workflow submits collected data via webhook on confirmation | Requires a new backend endpoint POST /api/submit-patient or reuse the webhook sender with a configured URL |
| WKFL-05 | Confirmation step shows all captured data and asks patient to verify | ui.ts showTranscriptionResult already has confirm/retry UI; needs a final "all fields" confirmation view |
| CTRL-01 | Operator can start/stop the entire system with a single button click | F2 shortcut exists but only toggles detector -- needs to also activate wake-lock and start idle video |
| CTRL-02 | Operator can emergency-stop everything with Escape key | Escape shortcut exists but only stops detector + releases wake-lock -- needs to also cancel workflow, hide video, reset UI |
| CTRL-03 | System auto-starts the detection pipeline when web app loads | Currently does NOT auto-start; needs an auto-start call on DOMContentLoaded |
| CTRL-04 | Web app monitors detector process health and shows status | Detector status badge exists in UI; needs periodic /api/process/status polling or WebSocket-based detection of crash |
| CTRL-05 | If detector crashes, web app displays alert with Restart button | WebSocket snapshot includes detector_running field; needs UI alert + restart action on state transition from running->stopped unexpectedly |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| TypeScript (vanilla) | 5.x | State machine logic | Project decision: no framework, kiosk app |
| Vite | 7.x | Build tool | Already configured in Phase 2 |
| FastAPI | 0.x | Backend endpoints | Already extended in Phase 1 |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| video.ts | Phase 3 | Video playback control | startIdleLoop, hideVideo, sequence control |
| audio.ts | Phase 4 | Recording + transcription | recordAndTranscribe with initial_prompt |
| ui.ts | Phase 4 | Transcription panel | showRecordingState, showProcessingState, showTranscriptionResult, hideTranscriptionPanel |
| api.ts | Phase 2 | API wrappers | apiStartDetector, apiStopDetector, apiWakeLockActivate, apiWakeLockRelease, apiDetectorStatus |
| state.ts | Phase 2 | Shared app state | appState.detector_running for status checks |
| shortcuts.ts | Phase 2 | Keyboard bindings | F2, Escape already registered |

### No New Dependencies
No new npm packages or pip packages needed. Phase 5 is pure orchestration of existing modules.

## Architecture Patterns

### Recommended Project Structure Changes
```
frontend/src/
  workflow.ts        # NEW: State machine — all workflow states, transitions, timeouts
  system-control.ts  # NEW: Start/stop/crash-recovery orchestration
  main.ts            # MODIFIED: Wire workflow + system-control into existing setup
  video.ts           # MODIFIED: Add pause/resume for recording windows
  api.ts             # MODIFIED: Add apiSubmitPatient endpoint wrapper
  types.ts           # MODIFIED: Add WorkflowState, PatientData types
  ro.ts              # MODIFIED: Add workflow-specific Romanian strings
  ui.ts              # MODIFIED: Add crash alert UI, confirmation summary view

api/
  process_manager.py # MODIFIED: Pass --no-dashboard to subprocess
dashboard/
  web.py             # MODIFIED: Add POST /trigger webhook relay endpoint
```

### Pattern 1: Explicit State Machine (No Library)

**What:** A TypeScript state machine using a discriminated union for states, with explicit transition functions and a central `dispatch(action)` method. No state machine library needed for ~12 states.

**When to use:** Always for this project. XState or similar libraries add 15-40KB and are overkill for a linear workflow with ~12 states.

**Example:**
```typescript
// workflow.ts — core state machine pattern
type WorkflowState =
  | 'stopped'
  | 'idle'
  | 'greeting'
  | 'ask_name'
  | 'recording_name'
  | 'show_name'
  | 'ask_question'
  | 'recording_question'
  | 'show_question'
  | 'ask_cnp'
  | 'recording_cnp'
  | 'show_cnp'
  | 'ask_email'
  | 'recording_email'
  | 'show_email'
  | 'confirm_all'
  | 'submitting'
  | 'farewell'
  | 'farewell_idle'
  | 'final';

interface PatientData {
  name: string | null;
  question: string | null;
  cnp: string | null;
  email: string | null;
}

let currentState: WorkflowState = 'stopped';
let patientData: PatientData = { name: null, question: null, cnp: null, email: null };
let stateTimeout: ReturnType<typeof setTimeout> | null = null;

function transition(newState: WorkflowState): void {
  clearTimeout(stateTimeout!);
  currentState = newState;
  // Start state-specific timeout
  stateTimeout = setTimeout(() => handleTimeout(), getTimeoutForState(newState));
  // Execute state entry action
  executeStateEntry(newState);
}
```

### Pattern 2: Video-Then-Record Sequence (from controller.py)

**What:** The controller.py `play_video_then_stt()` function defines the exact interaction pattern: play a question video to completion, then switch to idle video looping while recording speech, then show the transcription result.

**When to use:** After video3 (name), video6 (question), video7 (CNP), and video8 (email).

**Critical detail from controller.py:**
```python
# controller.py exact sequence:
play_video(VIDEO2)                    # greeting — no recording
play_video_then_stt(VIDEO3)           # ask name → record → show
play_video_then_stt(VIDEO6)           # ask question → record → show
play_video_then_stt(VIDEO7, prompt="1 2 3 4...")  # ask CNP → record → show
play_video_then_stt(VIDEO8, prompt="...", is_email=True)  # ask email → record → show
play_video(VIDEO4)                    # farewell
play_video_for(VIDEO1, 5)            # idle loop for 5 seconds
play_video(VIDEO5)                    # final goodbye
```

**Mapped to workflow states:**
```
idle → person_entered → greeting (video2)
  → video2 ends → ask_name (video3)
  → video3 ends → recording_name (idle video loops, mic records 10s)
  → recording done → show_name (transcription result, confirm/retry)
  → confirmed → ask_question (video6)
  → video6 ends → recording_question (idle loops, mic records)
  → confirmed → ask_cnp (video7)
  → video7 ends → recording_cnp (idle loops, mic records, prompt="1 2 3...")
  → confirmed → ask_email (video8)
  → video8 ends → recording_email (idle loops, mic records, prompt=email patterns)
  → confirmed → confirm_all (show all data, final confirmation)
  → confirmed → submitting (POST webhook)
  → submitted → farewell (video4)
  → video4 ends → farewell_idle (video1 loops for 5s)
  → 5s elapsed → final (video5)
  → video5 ends → idle (back to video1 loop)
```

### Pattern 3: System Control Orchestration

**What:** F2 press orchestrates multiple subsystems in sequence: start detector subprocess, activate wake-lock, initialize audio, start idle video loop. Escape reverses everything.

**Example:**
```typescript
// system-control.ts
async function startSystem(): Promise<void> {
  // 1. Start detector subprocess
  await apiStartDetector();
  // 2. Activate wake-lock
  await apiWakeLockActivate();
  // 3. Initialize audio (mic permission)
  if (!isMicReady()) await initAudio();
  // 4. Start idle video loop
  startIdleLoop();
  // 5. Begin health monitoring
  startHealthMonitor();
  // 6. Transition workflow to idle
  workflowTransition('idle');
}

async function stopSystem(): Promise<void> {
  // 1. Cancel any active workflow
  workflowTransition('stopped');
  // 2. Stop detector
  await apiStopDetector();
  // 3. Release wake-lock
  await apiWakeLockRelease();
  // 4. Hide video
  hideVideo();
  // 5. Hide transcription panel
  hideTranscriptionPanel();
  // 6. Stop health monitor
  stopHealthMonitor();
}
```

### Pattern 4: Crash Detection via WebSocket State Diff

**What:** The WebSocket snapshot already includes `detector_running: boolean`. The frontend tracks the previous value and detects unexpected transitions from `true` to `false` (crash). A polling fallback via `/api/process/status` runs every 5 seconds as a safety net.

**Example:**
```typescript
// system-control.ts
let wasDetectorRunning = false;
let healthInterval: ReturnType<typeof setInterval> | null = null;

function onStateUpdate(state: DashboardSnapshot): void {
  if (wasDetectorRunning && !state.detector_running) {
    // Unexpected stop — crash detected
    showCrashAlert();
  }
  wasDetectorRunning = state.detector_running;
}

function startHealthMonitor(): void {
  healthInterval = setInterval(async () => {
    const status = await apiDetectorStatus();
    if (!status.running && wasDetectorRunning) {
      showCrashAlert();
    }
  }, 5000);
}
```

### Anti-Patterns to Avoid

- **Putting workflow logic inside video.ts:** video.ts owns playback mechanics. Workflow decisions (which video plays after recording) belong in workflow.ts. Video.ts should expose primitives (`playVideo`, `startIdleLoop`, `onVideoEnded` callback) that workflow.ts calls.

- **Sharing state between modules via global variables:** Use explicit function calls and callbacks. workflow.ts calls video functions directly; it does not read video.ts internal state.

- **Using timers for video transitions:** The existing `onended` event pattern from Phase 3 is correct. workflow.ts hooks into video end events, not setTimeout for video durations.

- **Polling for transcription results:** recordAndTranscribe already returns a Promise. The workflow awaits it directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine library | XState/Robot import | Simple switch/object map | 12 linear states; library adds complexity + bundle size |
| Video end detection | Custom timer per video | `videoEl.addEventListener('ended', ...)` | Already working in Phase 3; event-driven is more reliable |
| Audio recording | Custom Web Audio pipeline | `recordAndTranscribe()` from audio.ts | Already implemented and tested in Phase 4 |
| Transcription UI | New DOM elements | `showRecordingState/showTranscriptionResult` | Already implemented in Phase 4 ui.ts |
| Process health check | Custom WebSocket messages | `/api/process/status` polling + `detector_running` from snapshot | Backend already provides both |

## Common Pitfalls

### Pitfall 1: Video Sequence vs Workflow Sequence Mismatch

**What goes wrong:** video.ts INSTRUCTION_SEQUENCE plays all 7 videos straight through (video2,3,6,7,8,4,5) without pausing for recording. Phase 5 needs to PAUSE after video3, video6, video7, and video8 for recording.

**Why it happens:** Phase 3 implemented a simple linear sequence for testing. Phase 5 needs the workflow to control each step individually.

**How to avoid:** The workflow state machine must NOT use `startInstructionSequence()` from video.ts. Instead, workflow.ts must call `playVideo(filename)` for each video individually and listen for the `ended` event to transition to the recording state. This means video.ts needs a new API: play a single video once and call a callback when it ends.

**Warning signs:** All videos play through without recording stops.

### Pitfall 2: Subprocess Dashboard Port Conflict

**What goes wrong:** process_manager.py starts main.py without `--no-dashboard`. The subprocess tries to start its own dashboard on port 8080, conflicting with the parent FastAPI process.

**Why it happens:** process_manager.py was built in Phase 1 before the subprocess architecture was fully designed.

**How to avoid:** Two options:
1. **Parent-dashboard mode:** Pass `--no-dashboard` to the subprocess. Add a webhook relay `/trigger` endpoint to the parent FastAPI. Configure `WEBHOOK_URL=http://localhost:8080/trigger` for the subprocess.
2. **Subprocess-dashboard mode:** Don't run the dashboard standalone. main.py IS the primary process. The process manager just restarts main.py (the whole thing).

**Recommendation:** Option 1 (parent-dashboard mode) is better because the frontend is served by the parent process and needs WebSocket from the parent's DashboardState. The subprocess sends webhooks to the parent's `/trigger` endpoint. The parent pushes events to the browser via WebSocket.

### Pitfall 3: Race Condition Between Video End and Recording Start

**What goes wrong:** When video3 ends (asking for name), the workflow transitions to recording_name. But if there's a delay before `recordAndTranscribe()` acquires the mic, the user might miss the beginning of their speech.

**Why it happens:** getUserMedia permission is already granted (Phase 4 init), but stream acquisition still takes ~100-500ms.

**How to avoid:** Show "Inregistrare..." UI immediately on video end, THEN start recording. The user sees the visual cue that recording is active. The idle video starts looping as background during recording. Small delay is acceptable since controller.py also had a transition gap.

### Pitfall 4: Timeout Cleanup Not Releasing Resources

**What goes wrong:** Patient walks away mid-recording. The timeout fires and transitions to idle, but MediaRecorder is still running. The mic indicator stays on, and the next patient cycle may fail.

**Why it happens:** setTimeout callback doesn't know about the active recording Promise.

**How to avoid:** Keep a reference to the active recording operation. On timeout, abort the recording (stop MediaRecorder, release tracks). Use an AbortController-like pattern:
```typescript
let activeAbort: (() => void) | null = null;

function handleTimeout(): void {
  if (activeAbort) activeAbort();
  resetPatientData();
  transition('idle');
}
```

### Pitfall 5: Escape During Recording Leaves Orphan Streams

**What goes wrong:** Operator presses Escape during an active recording. The detector stops and video hides, but MediaRecorder and mic tracks remain active.

**How to avoid:** The emergency stop function must explicitly cancel any active recording, release mic tracks, and hide the transcription panel BEFORE stopping the detector. The stop sequence must be: abort recording -> hide UI -> stop detector -> release wake-lock.

### Pitfall 6: CTRL-03 Auto-Start Requires User Gesture

**What goes wrong:** CTRL-03 requires auto-starting the system on page load. But `initAudio()` requires a user gesture for AudioContext creation and mic permission. Auto-start cannot initialize audio.

**How to avoid:** Auto-start the detector and wake-lock on page load (no gesture needed). Defer audio initialization to the first F2 press or first recording attempt. The system can run detection and video without audio. Audio initializes on the first user interaction.

### Pitfall 7: Multiple Patient Cycles Without Reset

**What goes wrong:** After the first patient completes, captured data (name, CNP, email) persists in JavaScript memory. The second patient sees stale data in confirmation screens.

**How to avoid:** Reset `patientData` to null values when transitioning to `idle` state. Also clear the transcription panel DOM. This must happen on both normal completion (farewell -> idle) and timeout/abort paths.

## Code Examples

### Example 1: Workflow State Machine Core

```typescript
// workflow.ts — core structure
import { recordAndTranscribe } from './audio.ts';
import type { TranscribeResult } from './types.ts';
import {
  showRecordingState,
  showProcessingState,
  showTranscriptionResult,
  hideTranscriptionPanel,
} from './ui.ts';

const STATE_TIMEOUTS: Record<string, number> = {
  greeting: 60_000,       // 60s for greeting video
  ask_name: 60_000,       // 60s for question video
  recording_name: 15_000, // 15s recording window (10s record + 5s buffer)
  show_name: 30_000,      // 30s to confirm
  // ... similar for other states
  confirm_all: 60_000,    // 60s to review all data
};

const RECORDING_PROMPTS: Record<string, { prompt?: string; isEmail?: boolean }> = {
  recording_name: {},
  recording_question: {},
  recording_cnp: { prompt: '1 2 3 4 5 6 7 8 9 1 2 3 4' },
  recording_email: {
    prompt: 'tudor.trocaru arond gmail punct com',
    isEmail: true,
  },
};
```

### Example 2: Video.ts Modifications Needed

```typescript
// video.ts — new export needed for workflow control
type VideoEndCallback = () => void;
let onEndedCallback: VideoEndCallback | null = null;

/**
 * Play a single video once and call the callback when it ends.
 * Used by workflow.ts to control individual video + recording steps.
 */
export function playSingleVideo(filename: string, onEnded: VideoEndCallback): void {
  onEndedCallback = onEnded;
  playVideo(filename, { loop: false });
}

// Modify the existing 'ended' handler:
videoEl.addEventListener('ended', () => {
  if (onEndedCallback) {
    const cb = onEndedCallback;
    onEndedCallback = null;
    cb();
  } else if (state === 'playing_sequence') {
    playNextInSequence();
  }
});
```

### Example 3: Webhook Relay Endpoint (Backend)

```typescript
// dashboard/web.py — new /trigger endpoint
@app.post("/trigger")
async def receive_trigger(request: Request) -> JSONResponse:
    """Receive webhook from detector subprocess, push to WebSocket clients."""
    payload = await request.json()
    event_type = payload.get("event", "unknown")
    if event_type == "person_entered":
        state.push_event({
            "event": "person_entered",
            "timestamp": payload.get("timestamp", ""),
            "person_id": payload.get("person_id", -1),
            "confidence": payload.get("confidence", 0),
            "snapshot": payload.get("snapshot", ""),
        })
    return JSONResponse(content={"status": "ok"})
```

### Example 4: Patient Data Submission

```typescript
// api.ts — new endpoint
export async function apiSubmitPatient(data: PatientData): Promise<{ status: string }> {
  return post<{ status: string }>('/api/submit-patient');
  // Or POST to the configured webhook URL with patient data
}
```

## Critical Architecture Decision: Subprocess Communication

### The Problem

When `process_manager.py` starts `main.py` as a subprocess, the subprocess creates its own `DashboardState` in its own memory space. The parent FastAPI process (which serves the frontend) has a DIFFERENT `DashboardState` that is empty. The frontend connects to the parent's WebSocket and sees no detection events.

### Current State

- `process_manager.py` starts `main.py` WITHOUT `--no-dashboard`
- Subprocess tries to start dashboard on port 8080 (conflicts with parent)
- No `/trigger` endpoint exists in parent's `web.py`
- `WEBHOOK_URL` in `config.py` defaults to `https://example.com/webhook`

### Recommended Solution

**Option A: Parent-Dashboard Mode (RECOMMENDED)**

1. Modify `process_manager.py` to pass `--no-dashboard` to the subprocess
2. Also pass `WEBHOOK_URL=http://localhost:8080/trigger` as environment variable
3. Add `POST /trigger` endpoint to `web.py` that pushes events to `DashboardState`
4. Frontend connects to parent's WebSocket, sees events relayed from subprocess

This is the correct architecture because:
- Frontend is served by the parent process
- WebSocket state comes from the parent's DashboardState
- The subprocess focuses on detection only
- Crash detection works because the parent knows the subprocess PID

**Impact on Phase 5:** Process manager modification + trigger endpoint are prerequisites for the workflow. Without them, `person_entered` events never reach the frontend.

### Alternative: Standalone main.py Mode

If the subprocess architecture proves too complex, the fallback is:
- Don't use `process_manager.py` at all
- Run `main.py` directly (it starts its own dashboard)
- F2 start/stop controls the detector loop, not the subprocess
- This would require a different approach to CTRL-01/CTRL-05

## State of the Art

| Old Approach (controller.py) | Current Approach (Phase 5) | Impact |
|-----|-----|-----|
| VLC RC socket for video control | HTML5 video element with event-driven transitions | More reliable, no external process |
| sounddevice for recording | MediaRecorder + Web Audio API | Works in browser, no Python audio dependency |
| Threading.Event for trigger | WebSocket person_entered event | Real-time push to browser |
| time.sleep for video durations | onended event callback | Drift-free, handles variable load |
| No timeout handling | Per-state setTimeout | Handles patient abandonment |
| No confirmation step | showTranscriptionResult with confirm/retry | Data quality improvement |
| No crash recovery | Process status polling + UI alert | Operator self-service recovery |

## Open Questions

1. **Subprocess communication architecture**
   - What we know: process_manager doesn't pass --no-dashboard; no /trigger endpoint exists
   - What's unclear: Whether the project intends main.py to be the primary process (with its own dashboard) or run headless as a subprocess
   - Recommendation: Implement Option A (parent-dashboard mode) with --no-dashboard + /trigger relay. This matches the architecture research's stated design.

2. **Patient data submission endpoint**
   - What we know: WKFL-04 says "submit via webhook on confirmation"
   - What's unclear: Where does patient data go? No target URL/database is specified
   - Recommendation: Create POST /api/submit-patient that logs data and optionally forwards to a configured PATIENT_WEBHOOK_URL. For v1, logging is sufficient.

3. **Timeout durations per state**
   - What we know: controller.py uses 10s recording time, no other timeouts
   - What's unclear: How long to wait for confirmation, what's appropriate for greeting video
   - Recommendation: 30-60 seconds per state as defaults, configurable via constants in workflow.ts

4. **video.ts refactoring scope**
   - What we know: The current INSTRUCTION_SEQUENCE in video.ts plays all videos linearly without recording pauses
   - What's unclear: Whether to modify the existing sequence mechanism or replace it entirely
   - Recommendation: Add a new `playSingleVideo(filename, onEnded)` export. The existing sequence can remain for testing (F4 trigger). Workflow uses single-video control.

5. **CTRL-03 auto-start on page load**
   - What we know: Requirement says "auto-starts detection pipeline when web app loads"
   - What's unclear: This conflicts with needing a user gesture for audio; also may not be desired in development
   - Recommendation: Auto-start detector + wake-lock on load. Defer audio init to first user gesture. Add a `?no-autostart` query param for development.

## Sources

### Primary (HIGH confidence)
- `controller.py` (lines 261-284) — exact workflow sequence, recording prompts, video order
- `frontend/src/video.ts` — current INSTRUCTION_SEQUENCE, playVideo, onended wiring
- `frontend/src/audio.ts` — recordAndTranscribe API, 10s recording duration
- `frontend/src/ui.ts` — transcription panel UI functions
- `frontend/src/api.ts` — existing API wrappers for process management + wake-lock
- `api/process_manager.py` — start_detector subprocess.Popen invocation
- `dashboard/web.py` — DashboardState.snapshot(), WebSocket endpoint, no /trigger endpoint

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — system overview, data flow diagrams
- `.planning/research/PITFALLS.md` — workflow timeout, transcription reliability concerns
- Phase 1-4 VERIFICATION.md files — confirmed working subsystems and wiring

## Metadata

**Confidence breakdown:**
- Workflow sequence: HIGH - directly from controller.py source code
- State machine pattern: HIGH - standard TypeScript pattern, no library needed
- Subprocess architecture: HIGH - verified by reading process_manager.py and web.py source
- System control wiring: HIGH - all API endpoints verified in Phase 1-2
- Crash recovery: MEDIUM - design pattern is standard, but edge cases (race conditions) need testing
- Patient data submission: LOW - no target endpoint/database specified in requirements

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain; all dependencies are project-internal)
