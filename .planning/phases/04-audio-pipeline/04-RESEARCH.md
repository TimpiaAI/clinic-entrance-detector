# Phase 4: Audio Pipeline - Research

**Researched:** 2026-03-05
**Domain:** Browser audio capture (MediaRecorder API), AudioContext lifecycle, backend transcription integration, confirmation UI
**Confidence:** HIGH

## Summary

Phase 4 builds the browser-to-backend audio pipeline: the frontend captures microphone audio via `MediaRecorder`, sends the WebM blob to `POST /api/transcribe`, and displays the transcription result (text, CNP, email) with a confirmation step. The backend endpoint already exists and works (Phase 1 built it), but it needs one enhancement: an optional `initial_prompt` parameter that controller.py uses to guide Whisper toward digits (for CNP) and email patterns. The frontend needs a new `audio.ts` module and a confirmation/result panel in the UI.

The critical technical challenge is the AudioContext/getUserMedia lifecycle. Chrome suspends AudioContext objects created before a user gesture, and `navigator.mediaDevices` requires a secure context (localhost qualifies). The "Start System" F2 keypress is the correct gesture to both request mic permission and resume/create the AudioContext. Recording itself uses the stop-and-collect pattern (no timeslice): `MediaRecorder.start()` without arguments, then `stop()` after the desired duration, yielding one complete WebM blob with valid container headers that faster-whisper can decode directly via ffmpeg.

Phase 4 does NOT wire recording into the video sequence -- that is Phase 5's workflow state machine responsibility. Phase 4 builds and tests the audio module in isolation: a function like `recordAndTranscribe(durationMs, initialPrompt?)` that can be called from anywhere, returning `{text, cnp, email}`. Phase 4 also adds the confirmation UI panel and the "recording active" / "processing" visual indicators. Phase 5 will call these functions at the right moments in the patient workflow.

**Primary recommendation:** Build `audio.ts` with stop-and-collect MediaRecorder pattern, add `initial_prompt` to `/api/transcribe`, create a confirmation panel with accept/reject, and test the full round-trip with a real microphone on localhost.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STT-01 | Browser captures audio from microphone via Web Audio API / MediaRecorder | MediaRecorder with `audio/webm;codecs=opus` MIME type, `getUserMedia({audio: true})`, stop-and-collect blob pattern |
| STT-02 | Audio is sent to Python backend for Faster Whisper transcription (Romanian language) | `POST /api/transcribe` already exists; send WebM blob as FormData; add `initial_prompt` optional parameter |
| STT-03 | Backend extracts CNP (Romanian national ID number) from transcribed speech | `extract_cnp()` already in `api/transcribe.py` -- no changes needed; `initial_prompt` with digit hints improves accuracy |
| STT-04 | Backend extracts email address from transcribed speech | `extract_email()` already in `api/transcribe.py` -- no changes needed; `initial_prompt` with email format hints improves accuracy |
| STT-05 | Transcription results are displayed to operator/patient with confirmation step | Confirmation panel UI showing text/CNP/email with accept/reject buttons; inline in the main feed area |
| STT-06 | Microphone permission is requested on operator's "Start System" gesture (user interaction required) | `getUserMedia()` called inside F2 handler (user gesture); `AudioContext` created/resumed in same handler |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| MediaRecorder API | Browser-native | Capture mic audio as WebM/Opus blob | No npm dependency needed; universal Chrome support since v49; `isTypeSupported()` for runtime verification |
| navigator.mediaDevices.getUserMedia | Browser-native | Request microphone access | Requires secure context (localhost qualifies); always returns a Promise |
| AudioContext | Browser-native | Audio lifecycle management | Needed only for state tracking (suspended/running); NOT needed for recording itself |
| FormData + fetch | Browser-native | POST audio blob to /api/transcribe | Standard multipart upload pattern; no libraries needed |

### Backend (existing, minor extension)

| Library | Version | Purpose | Change Needed |
|---------|---------|---------|---------------|
| faster-whisper | 1.2.1 (installed) | Romanian STT transcription | Add `initial_prompt` parameter to endpoint |
| python-multipart | installed | Parse multipart upload | No changes |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None | -- | -- | All APIs are browser-native; zero npm additions |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MediaRecorder (WebM) | AudioWorklet + manual PCM/WAV encoding | AudioWorklet gives raw PCM ideal for Whisper, but requires ~80 lines of AudioWorkletProcessor boilerplate + binary WebSocket. MediaRecorder WebM is simpler and faster-whisper accepts it via ffmpeg. |
| Stop-and-collect | Timesliced chunks | Timesliced chunks lack valid WebM headers after the first chunk. Stop-and-collect produces one valid file. For 10-second fixed recordings, there is zero benefit to streaming. |
| In-browser WAV conversion | Send WebM directly | Backend ffmpeg handles WebM-to-WAV transparently. In-browser WAV conversion would save ~100ms backend conversion time but adds ~60 lines of PCM-to-WAV encoding code. Not worth the complexity for 10-second clips. |

**Installation:**
```bash
# No npm packages needed -- all browser-native APIs
# No pip packages needed -- faster-whisper and python-multipart already installed
```

## Architecture Patterns

### Recommended Module Structure

```
frontend/src/
  audio.ts         # NEW: MediaRecorder + getUserMedia + transcribe API call
  api.ts           # EXTEND: add apiTranscribe() wrapper
  types.ts         # EXTEND: add TranscribeResult interface
  main.ts          # EXTEND: wire mic permission into F2 handler
  ui.ts            # EXTEND: add recording indicator + confirmation panel updates
  ro.ts            # EXTEND: add Romanian strings for audio states
  style.css        # EXTEND: add confirmation panel + recording indicator styles

api/
  transcribe.py    # EXTEND: add initial_prompt optional parameter
```

### Pattern 1: Stop-and-Collect MediaRecorder

**What:** Record audio without timeslice, collect one complete WebM blob on stop, POST to backend.
**When to use:** Always for this project. Fixed-duration recordings (10 seconds) do not benefit from streaming.
**Why this works:** When `MediaRecorder.start()` is called without a `timeslice` argument, calling `stop()` fires one `dataavailable` event with a complete, valid WebM file as the blob. This blob has proper container headers and is directly decodable by ffmpeg/faster-whisper.

```typescript
// audio.ts -- core recording function
export async function recordAudio(durationMs: number): Promise<Blob> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm';
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  recorder.start(); // No timeslice -- stop-and-collect

  await new Promise<void>((resolve) => setTimeout(resolve, durationMs));

  return new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      // Release mic immediately after recording
      stream.getTracks().forEach((t) => t.stop());
      resolve(new Blob(chunks, { type: mimeType }));
    };
    recorder.stop();
  });
}
```

### Pattern 2: AudioContext Lifecycle Guard

**What:** Create or resume AudioContext inside the F2 "Start System" user gesture handler. Check state before every recording.
**When to use:** Always. AudioContext created before user gesture is suspended by Chrome.
**Critical detail:** `getUserMedia()` does NOT require AudioContext to work. MediaRecorder works with the raw MediaStream. AudioContext is only needed if you want to analyze audio (e.g., level meter). For this project, AudioContext is used only as a lifecycle guard -- to ensure the audio subsystem is active.

```typescript
// audio.ts -- lifecycle management
let audioCtx: AudioContext | null = null;
let micPermissionGranted = false;

/**
 * Request mic permission and initialize audio subsystem.
 * MUST be called inside a user gesture handler (F2 keypress).
 */
export async function initAudio(): Promise<boolean> {
  // Create or resume AudioContext inside user gesture
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }

  // Pre-request mic permission so it is cached for later recordings
  try {
    const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    testStream.getTracks().forEach((t) => t.stop()); // Release immediately
    micPermissionGranted = true;
    return true;
  } catch (err) {
    console.error('audio: mic permission denied', err);
    micPermissionGranted = false;
    return false;
  }
}

export function isMicReady(): boolean {
  return micPermissionGranted;
}
```

### Pattern 3: Transcribe API Call with FormData

**What:** POST the WebM blob to `/api/transcribe` as multipart form data.
**When to use:** After every recording completes.

```typescript
// api.ts -- add transcribe wrapper
export interface TranscribeResult {
  text: string;
  cnp: string | null;
  email: string | null;
}

export async function apiTranscribe(
  audioBlob: Blob,
  initialPrompt?: string,
): Promise<TranscribeResult> {
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.webm');
  if (initialPrompt) {
    form.append('initial_prompt', initialPrompt);
  }

  const res = await fetch('/api/transcribe', { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`Transcribe failed: ${res.status}`);
  }
  return (await res.json()) as TranscribeResult;
}
```

### Pattern 4: Confirmation Panel UI

**What:** After transcription, display results and let operator/patient confirm or retry.
**When to use:** STT-05 requires a confirmation step before data is accepted.
**Design:** An overlay panel in the feed area (z-index between video and sidebar) showing the transcribed text, extracted CNP/email, and two buttons: "Confirma" (accept) and "Repeta" (retry). This panel uses the same opacity-based show/hide pattern as the video overlay and marquee.

```html
<!-- Add to index.html inside #app, after #text-overlay -->
<div id="transcription-panel">
  <div class="transcription-status" id="transcription-status">
    <!-- "Inregistrare...", "Procesare...", or result -->
  </div>
  <div class="transcription-result" id="transcription-result">
    <p class="result-text" id="result-text"></p>
    <p class="result-cnp" id="result-cnp"></p>
    <p class="result-email" id="result-email"></p>
  </div>
  <div class="transcription-actions" id="transcription-actions">
    <!-- Phase 5 will wire these buttons into the workflow -->
  </div>
</div>
```

### Pattern 5: Recording State Indicator

**What:** Visual feedback showing when recording is active ("Inregistrare...") and when processing ("Procesare...").
**When to use:** Always during recording and transcription. Patient must know when to speak.
**Design:** Reuse the existing marquee/text-overlay area or add a dedicated recording indicator positioned over the video feed area. A pulsing red dot + text is the standard pattern.

### Anti-Patterns to Avoid

- **Creating AudioContext at module load time:** Will be suspended. Create inside user gesture handler only.
- **Sending MediaRecorder chunks individually:** Only the first chunk has valid WebM headers. Always use stop-and-collect.
- **Forgetting to release MediaStream tracks:** `stream.getTracks().forEach(t => t.stop())` MUST be called after recording. Otherwise the mic stays open (red indicator in Chrome tab bar, potential audio feedback).
- **Not checking `MediaRecorder.isTypeSupported()`:** Hardcoding a MIME type that is not supported will throw at construction time.
- **Calling getUserMedia outside localhost:** `navigator.mediaDevices` is `undefined` on non-secure origins. Always verify `navigator.mediaDevices` exists before calling.
- **Re-creating AudioContext per recording:** Causes subtle latency and resource leaks. Create once, reuse across recordings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio recording | Custom AudioWorklet + PCM encoding | `MediaRecorder` with stop-and-collect | MediaRecorder handles all encoding; ~15 lines vs ~80+ for AudioWorklet |
| WebM-to-WAV conversion | In-browser PCM extraction + WAV header writing | Backend ffmpeg (already used by transcribe.py) | ffmpeg conversion adds <100ms; avoids ~60 lines of browser-side WAV encoding |
| Microphone permission UI | Custom permission dialog | Browser's native `getUserMedia()` prompt | Chrome handles the permission prompt; cannot be overridden in kiosk mode anyway |
| Audio format detection | Manual codec probing | `MediaRecorder.isTypeSupported()` | One-liner static method; returns boolean immediately |
| Exponential backoff for failed transcription | Custom retry logic | Simple single-retry with timeout | For 10-second clips, one retry is sufficient; complex retry adds UX confusion |

**Key insight:** The entire audio pipeline from mic to transcription result requires zero npm dependencies. Browser APIs + one backend endpoint + FormData is the complete solution.

## Common Pitfalls

### Pitfall 1: AudioContext Created Before User Gesture

**What goes wrong:** `new AudioContext()` at module load or DOMContentLoaded creates a suspended context. Recording appears to work but produces silent audio.
**Why it happens:** Chrome's autoplay policy applies to AudioContext. Contexts created before user interaction are suspended.
**How to avoid:** Create AudioContext lazily inside the F2 keypress handler (user gesture). Always check `audioCtx.state === 'running'` before recording.
**Warning signs:** Console warning "The AudioContext was not allowed to start"; `audioCtx.state` is `'suspended'`; Whisper returns empty text.

### Pitfall 2: getUserMedia Unavailable Outside Secure Context

**What goes wrong:** `navigator.mediaDevices` is `undefined` when page is served from a hostname other than `localhost`.
**Why it happens:** Chrome restricts getUserMedia to HTTPS or `localhost` (secure contexts) since Chrome 74.
**How to avoid:** Always access via `http://localhost:8080`. Add a startup guard in `audio.ts` that checks `navigator.mediaDevices` existence and shows a Romanian error message if missing.
**Warning signs:** `TypeError: Cannot read properties of undefined (reading 'getUserMedia')`; only reproduces when accessing via machine hostname.

### Pitfall 3: MediaRecorder Chunk Format Incompatible with Whisper

**What goes wrong:** Using `timeslice` in `MediaRecorder.start(timeslice)` produces chunks where only the first has valid WebM container headers. Sending individual chunks to Whisper fails.
**Why it happens:** WebM is a container format. Subsequent chunks are continuation fragments, not standalone files.
**How to avoid:** Use stop-and-collect: `start()` without timeslice, then `stop()`. The final `dataavailable` event produces a complete, valid WebM file.
**Warning signs:** Whisper returns empty text; backend logs show ffmpeg decode errors; works with manually created test files but fails with MediaRecorder output.

### Pitfall 4: MediaStream Not Released After Recording

**What goes wrong:** The browser's mic indicator stays active (red dot in Chrome tab). Potential audio feedback if speakers are near the mic. Resource leak over many recordings.
**Why it happens:** `MediaRecorder.stop()` stops recording but does NOT release the underlying `MediaStream`.
**How to avoid:** Always call `stream.getTracks().forEach(t => t.stop())` in the `onstop` handler.
**Warning signs:** Red mic indicator persists after recording; Chrome tab shows "this page is using your microphone" badge indefinitely.

### Pitfall 5: Missing initial_prompt for CNP/Email Accuracy

**What goes wrong:** Whisper transcribes digits as Romanian words ("unu doi trei") instead of numbers. Email addresses are garbled.
**Why it happens:** Without `initial_prompt`, Whisper has no context to prefer digits over words.
**How to avoid:** Pass `initial_prompt` to the transcribe endpoint. For CNP: `"1 2 3 4 5 6 7 8 9 1 2 3 4"` (biases toward digits). For email: `"tudor.trocaru arond gmail punct com, radu.popescu arond yahoo punct com"` (biases toward email patterns). These are the exact prompts used in controller.py.
**Warning signs:** CNP extraction returns null even when patient clearly says 13 digits; email extraction fails on common patterns.

### Pitfall 6: Race Condition Between stop() and onstop

**What goes wrong:** Code after `recorder.stop()` executes before `onstop` fires, trying to use the blob before it exists.
**Why it happens:** `MediaRecorder.stop()` is asynchronous. The `dataavailable` and `onstop` events fire after the current event loop tick.
**How to avoid:** Wrap the stop + blob collection in a Promise. Wait for `onstop` before returning the blob.
**Warning signs:** Blob is empty or undefined; chunks array has zero elements when accessed immediately after `stop()`.

## Code Examples

### Complete recordAndTranscribe Function

```typescript
// audio.ts
import { apiTranscribe, type TranscribeResult } from './api.ts';

const RECORD_DURATION_MS = 10_000;

/**
 * Record audio for a fixed duration, send to backend, return transcription.
 *
 * @param durationMs Recording duration in milliseconds (default: 10000)
 * @param initialPrompt Optional Whisper initial_prompt to bias transcription
 * @returns Transcription result with text, cnp, email
 */
export async function recordAndTranscribe(
  durationMs: number = RECORD_DURATION_MS,
  initialPrompt?: string,
): Promise<TranscribeResult> {
  // 1. Get mic stream
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  // 2. Create recorder with WebM/Opus
  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm';
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  // 3. Record for fixed duration
  recorder.start();
  await new Promise<void>((resolve) => setTimeout(resolve, durationMs));

  // 4. Stop and collect complete blob
  const blob = await new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      resolve(new Blob(chunks, { type: mimeType }));
    };
    recorder.stop();
  });

  // 5. Send to backend
  return apiTranscribe(blob, initialPrompt);
}
```

### Backend Extension: Add initial_prompt Parameter

```python
# api/transcribe.py -- modify the endpoint signature
from fastapi import APIRouter, File, Form, UploadFile

@router.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    initial_prompt: str | None = Form(None),
):
    """Accept an audio file (WebM/WAV), transcribe with Whisper, extract CNP and email."""
    model = get_model()

    suffix = ".webm"
    if audio.content_type and "wav" in audio.content_type:
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        kwargs: dict = {"language": "ro", "vad_filter": True}
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        segments, _ = model.transcribe(tmp_path, **kwargs)
        text = " ".join(s.text for s in segments).strip()
    finally:
        os.unlink(tmp_path)

    cnp = extract_cnp(text)
    email = extract_email(text)

    return {"text": text, "cnp": cnp, "email": email}
```

### Microphone Availability Guard

```typescript
// audio.ts -- call on module init or DOMContentLoaded
export function checkMicAvailability(): boolean {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.error('audio: getUserMedia not available (not a secure context?)');
    return false;
  }
  return true;
}
```

### F2 Handler Integration

```typescript
// main.ts -- extend the existing F2 handler
registerShortcut('F2', async () => {
  onUserGesture(); // Unmute video (existing)

  // Initialize audio on first Start press
  if (!isMicReady()) {
    const granted = await initAudio();
    if (!granted) {
      // Show Romanian error in status panel
      return;
    }
  }

  if (appState.detector_running) {
    await apiStopDetector();
  } else {
    await apiStartDetector();
  }
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `sounddevice` Python recording | Browser `MediaRecorder` | This phase | Recording happens in browser; no Python audio device conflicts; works in kiosk |
| Fixed 10s `sd.rec()` blocking call | `MediaRecorder` + `setTimeout` async | This phase | Non-blocking recording; UI can show progress indicator during capture |
| No confirmation step | Confirmation panel with accept/reject | This phase | Patient/operator verifies data before it is committed |
| No `initial_prompt` in API | `initial_prompt` as Form parameter | This phase | Frontend can pass context-specific hints for digits vs email |
| VLC marquee for "Ascultare..." | HTML div with recording/processing indicators | This phase | Native DOM; no external process dependency |

**Deprecated/outdated:**
- `sounddevice` for mic capture: Replaced by browser MediaRecorder. The Python process no longer needs mic access.
- Flask webhook on port 5050: Already replaced in Phase 1.
- VLC RC socket commands for marquee: Already replaced by HTML overlay in Phase 3.

## Integration Points

### Where Phase 4 Connects to Existing Code

| Integration | From | To | Mechanism |
|-------------|------|----|-----------|
| Mic init | `main.ts` F2 handler | `audio.ts initAudio()` | Function call inside user gesture |
| Recording trigger | Future `workflow.ts` (Phase 5) | `audio.ts recordAndTranscribe()` | Function call (Phase 4 exports, Phase 5 calls) |
| Transcription API | `audio.ts` | `api.ts apiTranscribe()` | FormData POST to `/api/transcribe` |
| Backend enhancement | `api/transcribe.py` | faster-whisper model | Add `initial_prompt` Form field |
| Recording indicator | `audio.ts` | `ui.ts` DOM updates | Show/hide "Inregistrare..." / "Procesare..." |
| Confirmation panel | `audio.ts` result | `ui.ts` DOM updates | Display text/CNP/email in panel |
| Marquee integration | `audio.ts` states | `video.ts showMarquee()` | Reuse existing marquee for "Ascultare..." / "Procesare..." labels |
| Video state check | `audio.ts` | `video.ts getVideoState()` | Only record when video state is appropriate (Phase 5 decides when) |

### What Phase 4 Does NOT Do (Phase 5 Responsibility)

- Does NOT decide when to start/stop recording in the video sequence
- Does NOT wire person_entered -> video -> recording -> video chain
- Does NOT implement workflow timeouts or patient abandonment
- Does NOT submit captured data via webhook

Phase 4 exports the building blocks. Phase 5 assembles them into the workflow.

## Confirmation UI Design

### Approach: Inline Overlay Panel

The confirmation panel overlays the feed/video area (same positioning strategy as the video overlay). It sits at z-index 15 (between video z=10 and text-overlay z=20).

**States:**
1. **Hidden** (default): `opacity: 0; pointer-events: none`
2. **Recording**: Shows pulsing red indicator + "Inregistrare..." text
3. **Processing**: Shows spinner + "Procesare..." text
4. **Result**: Shows transcribed text, extracted CNP/email, with Confirma/Repeta buttons
5. **Accepted**: Brief green flash, then hidden

**Romanian strings needed:**
```typescript
// Add to ro.ts
RECORDING: 'Inregistrare...',
PROCESSING: 'Procesare...',
CONFIRM_PROMPT: 'Este corect?',
CONFIRM_ACCEPT: 'Confirma',
CONFIRM_RETRY: 'Repeta',
CNP_LABEL: 'CNP',
EMAIL_LABEL: 'Email',
MIC_DENIED: 'Acces microfon refuzat',
MIC_UNAVAILABLE: 'Microfon indisponibil',
TRANSCRIPTION_EMPTY: 'Nu am inteles. Repetati va rog.',
```

### CSS Positioning

The panel should cover the central portion of the feed area (not the sidebar). The same `position: absolute` + `width: calc(100% - 300px)` pattern used by `#video-overlay` and `#text-overlay`.

## Recording Duration Consideration

controller.py uses `RECORD_TIME = 10` (10 seconds fixed). For Phase 4, keep this as the default. Phase 5 or later can implement VAD-based variable duration (Silero-VAD) as an enhancement. The 10-second fixed duration is proven to work in production.

## Cross-Platform Notes

### macOS (Development)
- `getUserMedia` works on `localhost` in Chrome and Safari
- Chrome mic permission prompt appears once, then cached per profile
- AudioContext resumes correctly inside keydown handler

### Windows 11 (Production)
- `getUserMedia` works on `localhost` in Chrome
- `--use-fake-ui-for-media-stream` flag auto-grants mic permission (no dialog)
- For kiosk mode: add this flag to Chrome launch script to avoid permission prompt blocking the patient flow
- Microphone device selection: Chrome uses the system default input device; configure Windows Sound Settings to set the correct mic before kiosk deployment

### Chrome Kiosk Mic Permission

In `--kiosk` mode, Chrome can show a permission prompt, but it is awkward to dismiss without a mouse. Two solutions:
1. **Preferred:** Add `--use-fake-ui-for-media-stream` to kiosk launch flags -- auto-grants mic/camera without prompt
2. **Alternative:** Grant permission once in the Chrome profile before enabling kiosk mode, using the same `--user-data-dir` path

## Open Questions

1. **Whisper model latency on clinic mini PC**
   - What we know: `medium` + `int8` is the current config; latency on developer Mac is 1-3 seconds
   - What's unclear: Latency on the Windows 11 mini PC (unknown CPU/RAM specs)
   - Recommendation: Show "Procesare..." indicator during transcription. If latency exceeds 15 seconds on target hardware, downgrade to `small` model. This is a Phase 4 testing concern, not a code architecture concern.

2. **Should recording duration be configurable per-recording?**
   - What we know: controller.py uses fixed 10 seconds for all recordings
   - What's unclear: Whether shorter/longer durations are needed per recording type
   - Recommendation: Make `durationMs` a parameter of `recordAndTranscribe()` with a default of 10000. Phase 5 can pass different durations if needed.

3. **Error handling for transcription failure**
   - What we know: Network errors, model loading errors, empty audio can cause failures
   - Recommendation: Return a clear error state from `recordAndTranscribe()`. Display "Nu am inteles. Repetati va rog." in the confirmation panel. Phase 5 decides whether to retry or skip.

## Sources

### Primary (HIGH confidence)
- [MDN MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) - stop-and-collect pattern, mimeType, dataavailable event
- [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) - secure context requirement, permission model
- [MDN AudioContext.resume()](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/resume) - suspended state, user gesture requirement
- [Chrome Autoplay Policy](https://developer.chrome.com/blog/autoplay) - AudioContext autoplay restrictions
- [MDN Web Audio Best Practices](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices) - AudioContext lifecycle
- Existing codebase: `api/transcribe.py` (Phase 1), `controller.py` (original workflow + initial_prompt usage), `frontend/src/video.ts` (Phase 3)

### Secondary (MEDIUM confidence)
- [Chrome getUserMedia in 2025](https://blog.addpipe.com/getusermedia-getting-started/) - secure context, kiosk mode permissions
- [Chrome kiosk mic permission](http://www.note.id.lv/2015/07/Chrome-access-to-webcam-always.html) - `--use-fake-ui-for-media-stream` flag
- [Whisper audio format support](https://github.com/openai/whisper/discussions/2292) - WebM accepted via ffmpeg
- [MediaRecorder chunk format issue](https://github.com/chrisguttandin/extendable-media-recorder/issues/638) - why stop-and-collect is required

### Tertiary (LOW confidence)
- Whisper `initial_prompt` effectiveness for Romanian digits: based on controller.py production usage, not benchmarked

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all browser-native APIs verified via MDN, backend endpoint already exists and tested
- Architecture: HIGH - stop-and-collect pattern is well-documented; integration points clearly defined from existing code
- Pitfalls: HIGH - AudioContext suspension, secure context, WebM chunk format all verified against MDN and Chrome docs
- Confirmation UI: MEDIUM - design pattern is standard but exact layout/z-index needs implementation testing

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable browser APIs, no expected breaking changes)
