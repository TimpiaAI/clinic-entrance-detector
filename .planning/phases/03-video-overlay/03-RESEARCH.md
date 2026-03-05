# Phase 3: Video Overlay - Research

**Researched:** 2026-03-05
**Domain:** HTML5 video overlay, CSS z-index stacking, event-driven video sequencing, marquee text overlay
**Confidence:** HIGH

## Summary

Phase 3 replaces the VLC RC socket video controller (`controller.py`) with browser-native HTML5 `<video>` playback overlaid on the MJPEG detection feed using CSS z-index stacking. The existing codebase already has all backend infrastructure in place: Phase 1 built the `/api/videos/{filename}` endpoint with HTTP 206 range support and an ALLOWED_VIDEOS whitelist (video1-8.mp4), and Phase 2 built the MJPEG fetch-to-canvas renderer, WebSocket client with backoff reconnect, shared state module, and keyboard shortcuts. The remaining work is purely frontend: a `video.ts` module that manages a single `<video>` element, a video sequence state machine that transitions between idle loop and instructional videos based on WebSocket `person_entered` events, a CSS marquee text overlay, and DOM/CSS layout changes to stack the layers correctly.

The original `controller.py` defines the exact video sequence: idle loop on `video1.mp4` -> on trigger: `video2.mp4` (greeting) -> `video3.mp4` (ask name) -> `video6.mp4` (ask something) -> `video7.mp4` (ask CNP) -> `video8.mp4` (ask email) -> `video4.mp4` (farewell) -> `video5.mp4` (final) -> back to idle. Each transition happens when the previous video ends (`onended` event in HTML5, replacing VLC's time-based `sleep(duration)` approach). The marquee text overlay replaces VLC's `marq-marquee` RC command with a positioned `<div>` above the video layer.

**Primary recommendation:** Reuse a single `<video>` element (change `src`, call `load()`, then `play()`) rather than creating/destroying elements. Use `loop` attribute only for the idle video (video1.mp4). For instructional videos, remove `loop` and wire `onended` for transitions. Always `await video.play()` with catch for autoplay failure resilience.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VCTL-01 | 8 instructional videos (video1-8.mp4) play in the same browser window overlaid on the camera feed | CSS z-index stacking pattern (Pattern 2 from ARCHITECTURE.md); single `<video>` element positioned absolutely over the MJPEG canvas; `/api/videos/{filename}` endpoint already serving files with range support |
| VCTL-02 | Video playback is triggered automatically by entrance detection webhook events | WebSocket `person_entered` events already arrive in `event_log` array via `state.ts`; video.ts watches for new `person_entered` events and initiates the instructional sequence |
| VCTL-03 | Idle video loops continuously when no patient workflow is active | `video1.mp4` plays with `loop` attribute set on the `<video>` element; `onended` does NOT fire when `loop=true` (MDN confirmed) so idle state is naturally stable |
| VCTL-04 | Text overlays (marquee) display extracted patient data during video playback | Positioned `<div>` at z-index 3 (above video at z-index 2) with CSS animation for scrolling effect; replaces VLC `marq-marquee` RC command |
| VCTL-05 | Video transitions are event-driven (onended callback), not time-based | Each instructional video registers `onended` handler that advances to next video in sequence; `loop` attribute is removed for instructional videos so `onended` fires correctly |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| HTML5 `<video>` | Browser-native | Video playback of video1-8.mp4 | Zero dependencies; plays mp4 natively in all Chromium browsers; `onended` event for sequencing; `loop` attribute for idle state |
| CSS `position: absolute` + `z-index` | Browser-native | Layer stacking: canvas (z1) / video (z2) / text overlay (z3) | Standard CSS; no library needed; already documented in ARCHITECTURE.md Pattern 2 |
| CSS `@keyframes` + `animation` | Browser-native | Marquee scrolling text effect | Replaces deprecated `<marquee>` tag; hardware-accelerated via `transform: translateX()` |
| `/api/videos/{filename}` | Phase 1 | HTTP 206 range-enabled video serving | Already built and tested in Phase 1; ALLOWED_VIDEOS whitelist prevents arbitrary file access |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `state.ts` (existing) | Phase 2 | Shared app state with `event_log` array | Detect new `person_entered` events by comparing event_log length/contents |
| `ws.ts` (existing) | Phase 2 | WebSocket client with backoff reconnect | Receives `DashboardSnapshot` including `event_log` every 0.5s |
| `ro.ts` (existing) | Phase 2 | Romanian string constants | Add video-related Romanian strings (marquee text labels) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single `<video>` with src swap | Multiple `<video>` elements preloaded | Multiple elements consume more memory; Chromium bug 41462045 documents leaks when creating/removing video elements; single element + `load()` is W3C recommended |
| CSS `@keyframes` marquee | JavaScript requestAnimationFrame marquee | CSS animation is GPU-accelerated and simpler; JS would add code for no benefit; CSS `prefers-reduced-motion` media query handles accessibility |
| `onended` event transitions | `setTimeout(duration)` transitions | `onended` is specification-correct and robust; VLC controller used `sleep(duration)` because VLC RC had no end-event callback; HTML5 video provides this natively |

**Installation:**
```bash
# No additional packages needed -- all browser-native APIs
# Video files (video1-8.mp4) already exist in project root
# /api/videos/{filename} endpoint already built in Phase 1
```

## Architecture Patterns

### Recommended Layer Structure

```
#app (CSS grid container - existing)
  #feed-canvas              z-index: 1   (MJPEG detection feed - existing)
  #video-overlay            z-index: 10  (<video> element for instructional videos)
  #text-overlay             z-index: 20  (marquee text div)
  #status-panel             z-index: 30  (operator sidebar - existing)
  #entry-log                z-index: 30  (operator log - existing)
  #shortcuts-hint           z-index: 30  (bottom bar - existing)
```

Note: z-index values are elevated from the `1/2/3` in ARCHITECTURE.md to `1/10/20/30` to provide insertion room and avoid stacking context collisions with existing sidebar elements (status-panel, entry-log already at z-index: 2).

### Pattern 1: Single Video Element with Src Swap

**What:** Reuse one `<video>` element for all playback. Change `src`, call `load()`, then `play()` to switch videos. This is the W3C recommended approach and avoids Chromium memory leak issues with dynamic element creation/destruction.

**When to use:** Always. Never create/destroy `<video>` elements dynamically.

**Example:**
```typescript
// video.ts
const video = document.getElementById('video-overlay') as HTMLVideoElement;

async function playVideo(filename: string, opts: { loop?: boolean } = {}): Promise<void> {
  video.loop = opts.loop ?? false;
  video.src = `/api/videos/${filename}`;
  video.load();
  video.style.opacity = '1';
  try {
    await video.play();
  } catch (err) {
    console.error('video: autoplay blocked', err);
  }
}

function hideVideo(): void {
  video.style.opacity = '0';
  video.pause();
  video.removeAttribute('src');
  video.load(); // Release buffered data per W3C spec
}
```
Source: [MDN HTMLMediaElement](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video), [web.dev preload](https://web.dev/fast-playback-with-preload/)

### Pattern 2: Event-Driven Video Sequence State Machine

**What:** A simple state machine in `video.ts` that tracks which video is currently playing and what comes next. Transitions are driven by the `onended` event on the `<video>` element. The idle state uses `loop=true` (which suppresses `onended` per MDN spec).

**When to use:** For the instructional video sequence (VCTL-02, VCTL-05).

**Example:**
```typescript
// Video sequence from controller.py workflow():
const INSTRUCTION_SEQUENCE = [
  'video2.mp4',  // greeting
  'video3.mp4',  // ask name
  'video6.mp4',  // ask (question)
  'video7.mp4',  // ask CNP
  'video8.mp4',  // ask email
  'video4.mp4',  // farewell
  'video5.mp4',  // final
];
const IDLE_VIDEO = 'video1.mp4';

type VideoState = 'idle' | 'playing_sequence';

let state: VideoState = 'idle';
let sequenceIndex = 0;

function startIdleLoop(): void {
  state = 'idle';
  sequenceIndex = 0;
  playVideo(IDLE_VIDEO, { loop: true });
}

function startInstructionSequence(): void {
  if (state === 'playing_sequence') return; // Already in sequence
  state = 'playing_sequence';
  sequenceIndex = 0;
  playNextInSequence();
}

function playNextInSequence(): void {
  if (sequenceIndex >= INSTRUCTION_SEQUENCE.length) {
    startIdleLoop();
    return;
  }
  const filename = INSTRUCTION_SEQUENCE[sequenceIndex];
  sequenceIndex++;
  playVideo(filename, { loop: false });
}

// Wire onended to advance sequence
video.addEventListener('ended', () => {
  if (state === 'playing_sequence') {
    playNextInSequence();
  }
  // onended does NOT fire when loop=true, so idle state is naturally stable
});
```

### Pattern 3: Person-Entered Detection via Event Log Diffing

**What:** The frontend detects `person_entered` events by watching the `event_log` array in the WebSocket state snapshot. The video module needs to detect when a NEW `person_entered` event appears (not just any event_log change).

**When to use:** For triggering the instructional sequence (VCTL-02).

**Critical detail:** The existing `event_log` in `DashboardSnapshot` contains ALL event types (`person_entered`, `person_exited`, `test_webhook`, etc.). The video trigger must filter for `event === 'person_entered'` specifically. The entry log in `ui.ts` already tracks `lastEventCount` for incremental rendering -- a similar pattern works for video triggers, but tracking `lastPersonEnteredCount` separately.

**Example:**
```typescript
// In the state update callback (main.ts or video.ts)
let lastPersonEnteredTimestamp: string | null = null;

function checkForPersonEntered(eventLog: EventLogEntry[]): void {
  // event_log is newest-first (deque appendleft in Python)
  const latest = eventLog.find(e => e.event === 'person_entered');
  if (!latest) return;
  if (latest.timestamp === lastPersonEnteredTimestamp) return; // Already handled
  lastPersonEnteredTimestamp = latest.timestamp;
  startInstructionSequence();
}
```

### Pattern 4: CSS Marquee Text Overlay

**What:** A `<div>` positioned above the video (z-index 20) displays scrolling text. Uses CSS `@keyframes` with `transform: translateX()` for smooth GPU-accelerated animation. Replaces VLC's `marq-marquee` command.

**When to use:** For VCTL-04 (text overlays during video playback).

**Example:**
```css
#text-overlay {
  position: absolute;
  bottom: 8%;
  left: 0;
  width: 100%;
  z-index: 20;
  overflow: hidden;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}

#text-overlay .marquee-content {
  display: inline-block;
  white-space: nowrap;
  font-size: 36px;
  font-weight: 700;
  color: #ffffff;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
  animation: marquee-scroll 12s linear infinite;
}

@keyframes marquee-scroll {
  0%   { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
```

```typescript
function showMarquee(text: string): void {
  const overlay = document.getElementById('text-overlay')!;
  const content = overlay.querySelector('.marquee-content')!;
  content.textContent = text;
  overlay.style.opacity = '1';
}

function hideMarquee(): void {
  const overlay = document.getElementById('text-overlay')!;
  overlay.style.opacity = '0';
}
```
Source: [CSS Marquee without marquee tag (w3docs)](https://www.w3docs.com/snippets/css/how-to-have-the-marquee-effect-without-using-the-marquee-tag-with-css-javascript-and-jquery.html), [CSS animations (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/animation)

### Anti-Patterns to Avoid

- **Creating/destroying `<video>` elements per video:** Causes Chromium memory leaks (documented in Chromium issue 41462045). Always reuse a single element and change `src`.
- **Using `loop` attribute on instructional videos:** The `onended` event does NOT fire when `loop=true` (MDN confirmed). Instructional videos MUST have `loop=false` for sequencing to work.
- **Using deprecated `<marquee>` tag:** Removed from HTML spec. Use CSS `@keyframes` animation with `transform: translateX()`.
- **Hiding video with `display: none` during transitions:** Can cause the browser to release buffered data. Use `opacity: 0` for visibility toggling (consistent with existing `feed.ts` pattern for MJPEG canvas).
- **Controlling video from Python/backend:** All video playback logic must be browser-side. Backend only sends high-level events (`person_entered`). The JS state machine decides what plays when. (Anti-Pattern 1 from ARCHITECTURE.md.)
- **Using `video.src = ''` to "stop" playback:** This triggers a network error event. Instead: `video.pause()`, `video.removeAttribute('src')`, `video.load()` per W3C spec to release resources.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video playback | Custom canvas-based video renderer | HTML5 `<video>` element | Browser handles decoding, buffering, seeking, and format negotiation natively |
| Scrolling text | JavaScript requestAnimationFrame loop | CSS `@keyframes` + `transform: translateX()` | GPU-accelerated, no JS overhead, respects `prefers-reduced-motion` |
| Video seeking/range requests | Custom byte-range fetcher in JS | Browser-native range request via `<video src="/api/videos/...">` | Chrome automatically sends Range headers when seeking; Phase 1 endpoint handles 206 responses |
| Video duration detection | ffprobe subprocess (like controller.py) | `onended` event / `video.duration` property | Browser knows the exact duration from the mp4 container metadata; no need for server-side ffprobe |
| Event detection | Custom WebSocket event filtering protocol | Diff `event_log` array from existing `DashboardSnapshot` | The WebSocket already pushes the full event log every 0.5s; no new protocol needed |

**Key insight:** The entire VLC RC socket protocol (connect, send commands, parse responses, manage duration timers) is replaced by three browser APIs: `<video>` element, `onended` event, and CSS. The complexity reduction is dramatic.

## Common Pitfalls

### Pitfall 1: `onended` Not Firing When `loop=true`

**What goes wrong:** Developer sets `loop` attribute on all videos for "safety" and `onended` never fires, so the instructional sequence never advances.
**Why it happens:** Per MDN spec, the `ended` event does not fire when the `loop` property is `true` and `playbackRate` is non-negative. This is correct browser behavior.
**How to avoid:** Only set `loop=true` on the idle video (video1.mp4). All instructional videos must have `loop=false`. Explicitly set `video.loop = false` before each instructional video plays.
**Warning signs:** Video plays to end and restarts instead of advancing to next video; `onended` listener never fires.

### Pitfall 2: Video Autoplay Blocked on Cold Kiosk Boot

**What goes wrong:** After a power cycle, Chrome kiosk opens the page and the idle video does not play. The patient sees a black screen. `video.play()` rejects with `NotAllowedError`.
**Why it happens:** Chrome autoplay policy requires either (a) the video is muted, or (b) a user gesture occurred, or (c) `--autoplay-policy=no-user-gesture-required` launch flag is set. On cold boot, no user gesture has occurred.
**How to avoid:** Always `await video.play()` with a `.catch()` handler. For production kiosk, add `--autoplay-policy=no-user-gesture-required` to Chrome launch flags (Phase 6 responsibility, but video.ts must handle the error gracefully NOW). In development, the operator's first F2 keypress counts as a user gesture.
**Warning signs:** Console shows `NotAllowedError: play() failed because the user didn't interact with the document first`. Video element shows poster or frozen first frame.

### Pitfall 3: Memory Leak from Dynamic Video Element Creation

**What goes wrong:** Creating a new `<video>` element for each video in the sequence causes memory to grow. After 8+ patient cycles, the browser tab slows or crashes.
**Why it happens:** Chromium's garbage collection does not always promptly release video decoder resources when elements are removed from DOM (Chromium issue 41462045).
**How to avoid:** Reuse a single `<video>` element. Change `src`, call `load()`, then `play()`. When hiding, call `pause()`, `removeAttribute('src')`, `load()` to release buffers.
**Warning signs:** Chrome Task Manager shows memory growing after each patient cycle; video playback becomes choppy after several hours.

### Pitfall 4: Race Condition Between Person-Entered Events During Active Sequence

**What goes wrong:** While an instructional sequence is playing for Patient A, Patient B enters and triggers another `person_entered` event. The sequence restarts or plays two videos simultaneously.
**Why it happens:** The `person_entered` event listener doesn't check if a sequence is already active.
**How to avoid:** Guard the trigger: `if (state === 'playing_sequence') return;`. Ignore new `person_entered` events during an active sequence. The video state machine variable (`state`) provides this guard naturally.
**Warning signs:** Videos restart mid-sequence; two audio streams play simultaneously.

### Pitfall 5: Stale Event Log Causing Phantom Triggers on Reconnect

**What goes wrong:** After a WebSocket disconnect and reconnect, the full `event_log` is re-sent. The video module sees "new" `person_entered` events that already happened, and starts an unwanted sequence.
**Why it happens:** On reconnect, `resetEntryLog()` is called (existing Phase 2 behavior) and the full snapshot arrives. The video module's `lastPersonEnteredTimestamp` tracking must survive reconnects.
**How to avoid:** Track the last processed `person_entered` timestamp. On reconnect, compare the latest event timestamp -- only trigger if it is genuinely new (more recent than the last processed one). Using ISO timestamp comparison works because backend uses UTC ISO format.
**Warning signs:** Video sequence starts unexpectedly after a brief network hiccup.

### Pitfall 6: CSS Stacking Context Collision with Existing Sidebar

**What goes wrong:** The video or text overlay appears behind the status panel or entry log sidebar because of CSS stacking context rules.
**Why it happens:** The existing `#status-panel` and `#entry-log` have `z-index: 2`. If the video also uses `z-index: 2`, the stacking order depends on DOM source order, which can produce unexpected results.
**How to avoid:** Use well-separated z-index values: feed canvas (1), video (10), text overlay (20), sidebar/controls (30). The sidebar must always be on top so the operator can see system status even during video playback.
**Warning signs:** Operator cannot see the status panel when a video is playing; text overlay appears behind the video.

## Code Examples

Verified patterns from official sources and existing codebase analysis:

### Video Element HTML (add to index.html)

```html
<!-- Inside #app, after #feed-canvas, before #status-panel -->
<video id="video-overlay" playsinline preload="metadata" muted></video>
<div id="text-overlay">
  <span class="marquee-content"></span>
</div>
```

Note: `muted` attribute is set initially to ensure autoplay works in development (without `--autoplay-policy` flag). The video module will unmute when a user gesture has occurred (F2 start button). `playsinline` prevents iOS fullscreen (not relevant for Windows kiosk but good practice).

### Video CSS (add to style.css)

```css
/* Source: ARCHITECTURE.md Pattern 2, adapted for existing grid layout */
#video-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: calc(100% - 300px); /* Same width as feed-canvas, excluding sidebar */
  height: calc(100% - 30px); /* Exclude shortcuts-hint bar */
  object-fit: contain;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.3s;
  background: #000;
  pointer-events: none;
}

#text-overlay {
  position: absolute;
  bottom: 12%;
  left: 0;
  width: calc(100% - 300px);
  z-index: 20;
  overflow: hidden;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}

#text-overlay .marquee-content {
  display: inline-block;
  white-space: nowrap;
  padding-left: 100%;
  font-size: 36px;
  font-weight: 700;
  color: #ffffff;
  text-shadow: 2px 2px 6px rgba(0, 0, 0, 0.9);
  animation: marquee-scroll 12s linear infinite;
}

@keyframes marquee-scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-100%); }
}

/* Responsive: when sidebar stacks below, video takes full width */
@media (max-width: 768px) {
  #video-overlay,
  #text-overlay {
    width: 100%;
  }
  #video-overlay {
    height: auto;
  }
}
```

### Video Sequence (ported from controller.py)

```typescript
// controller.py workflow() translates to:
// 1. idle_loop()         -> playVideo('video1.mp4', { loop: true })
// 2. play_video(VIDEO2)  -> playVideo('video2.mp4')   // greeting
// 3. play_video(VIDEO3)  -> playVideo('video3.mp4')   // ask name
//    (then STT recording - Phase 4, skip for now)
// 4. play_video(VIDEO6)  -> playVideo('video6.mp4')   // ask question
//    (then STT recording)
// 5. play_video(VIDEO7)  -> playVideo('video7.mp4')   // ask CNP
//    (then STT recording)
// 6. play_video(VIDEO8)  -> playVideo('video8.mp4')   // ask email
//    (then STT recording)
// 7. play_video(VIDEO4)  -> playVideo('video4.mp4')   // farewell
// 8. play_video(VIDEO5)  -> playVideo('video5.mp4')   // final
// 9. -> back to idle_loop()
//
// NOTE: STT recording between videos is Phase 4 (audio pipeline).
// Phase 3 plays all 8 videos sequentially without pausing for STT.
// Phase 5 (workflow state machine) will insert STT pauses between videos.
```

### Unmute on User Gesture

```typescript
// The video starts muted for autoplay compatibility.
// Unmute after the operator's first interaction (F2 start).
let userGestureReceived = false;

function onUserGesture(): void {
  if (userGestureReceived) return;
  userGestureReceived = true;
  const video = document.getElementById('video-overlay') as HTMLVideoElement;
  video.muted = false;
}

// Wire to F2 (start/stop toggle) -- the operator's first deliberate action
// This is called from main.ts alongside the existing F2 handler
```

## State of the Art

| Old Approach (controller.py) | Current Approach (Phase 3) | Why Changed |
|------------------------------|----------------------------|-------------|
| VLC RC socket commands (`add`, `repeat on/off`, `clear`) | `video.src = ...`, `video.loop = ...`, `video.load()`, `video.play()` | VLC RC is fragile (socket timeouts, lost commands); HTML5 video is browser-native and event-driven |
| `time.sleep(duration + 0.5)` for video end detection | `video.addEventListener('ended', ...)` | Event-driven is exact; sleep-based requires ffprobe duration lookup and adds 0.5s safety padding |
| `marq-marquee` VLC RC command for text overlay | CSS `@keyframes` + positioned `<div>` | Browser-native, GPU-accelerated, no external process dependency |
| `get_duration(video)` via ffprobe subprocess | `video.duration` property | Browser reads duration from mp4 container; no subprocess needed |
| `trigger_event = threading.Event()` + Flask webhook | WebSocket `event_log` diff from existing `DashboardSnapshot` | No separate process, no HTTP listener; events flow through existing WebSocket channel |
| Separate VLC window overlaid on screen via `--video-on-top` | CSS z-index stacking within same browser window | Single window; no window management; no focus stealing issues |

**Deprecated/outdated:**
- VLC RC socket interface: The entire `_rc_connect()`, `_rc_cmd()`, `play_video()`, `play_video_loop()`, `play_video_for()` pattern from controller.py is obsolete. HTML5 `<video>` replaces all of it.
- `<marquee>` HTML tag: Removed from HTML spec. Use CSS `@keyframes` animation.

## Open Questions

1. **Video playback order between videos 3-8 for STT integration**
   - What we know: `controller.py` plays videos 2,3,6,7,8,4,5 (not sequential 2,3,4,5,6,7,8). Between some videos (3,6,7,8), it records speech. Phase 3 plays them all sequentially without STT pauses.
   - What's unclear: Will Phase 5 (workflow state machine) insert pauses between specific videos for STT, or will the sequence be restructured?
   - Recommendation: For Phase 3, implement the exact controller.py sequence (2,3,6,7,8,4,5) so the video ordering is correct. Phase 5 will insert STT pauses between specific steps. The sequence array should be easy to modify.

2. **Muted vs unmuted autoplay in development**
   - What we know: Chrome blocks autoplay with sound unless `--autoplay-policy=no-user-gesture-required` is set (kiosk flag) or a user gesture occurred. In development, the operator clicks F2.
   - What's unclear: A Chrome Community thread (2024) reports `--autoplay-policy` flag may not be respected in some Chrome versions.
   - Recommendation: Start muted (`muted` attribute), unmute after first user gesture (F2 keypress). This works in both development and kiosk. Phase 6 (kiosk hardening) will validate the `--autoplay-policy` flag on the production machine. If the flag works, videos can autoplay with sound from cold boot.

3. **Text overlay content for Phase 3 vs Phase 5**
   - What we know: `controller.py` uses `show_marquee("Ascultare...")` during recording and `show_marquee(result, duration_ms=5000)` to show transcription results. These are Phase 4/5 behaviors.
   - What's unclear: What text should the marquee show during Phase 3 (before STT is implemented)?
   - Recommendation: Phase 3 implements the marquee infrastructure (show/hide/scroll) and demonstrates it with static Romanian text labels per video (e.g., "Bine ati venit" during greeting, "Va rugam spuneti numele" during ask-name). Phase 4/5 will replace these with dynamic content.

## Sources

### Primary (HIGH confidence)
- [MDN HTMLMediaElement ended event](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/ended_event) - confirmed `onended` does NOT fire when `loop=true`
- [MDN `<video>` element](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video) - preload, autoplay, loop behavior
- [MDN HTMLMediaElement preload property](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/preload) - `metadata` vs `auto` vs `none`
- [Chrome Autoplay Policy](https://developer.chrome.com/blog/autoplay) - `NotAllowedError`, `--autoplay-policy` flag
- [web.dev preload for fast playback](https://web.dev/fast-playback-with-preload/) - preload strategies, `load()` method
- Existing codebase: `controller.py` (video sequence logic), `dashboard/web.py` (video endpoint), `frontend/src/state.ts` (event_log)

### Secondary (MEDIUM confidence)
- [Chromium issue 41462045](https://issues.chromium.org/issues/41462045) - memory leak when replacing video elements (status: tracked since Chrome 74)
- [Chrome Community thread on --autoplay-policy](https://support.google.com/chrome/thread/207847413/) - reports of flag not being respected in some versions; resolution unclear
- [w3docs CSS marquee without tag](https://www.w3docs.com/snippets/css/how-to-have-the-marquee-effect-without-using-the-marquee-tag-with-css-javascript-and-jquery.html) - CSS @keyframes alternative
- [CSS Marquee effect](https://www.bennadel.com/blog/4536-creating-a-marquee-effect-with-css-animations.htm) - CSS animation implementation
- [Mux video playback best practices 2025](https://www.mux.com/articles/best-practices-for-video-playback-a-complete-guide-2025) - preload strategies for multiple videos
- ARCHITECTURE.md Pattern 2 (project research) - CSS z-index stacking layout
- PITFALLS.md Pitfall 2 (project research) - autoplay failure handling

### Tertiary (LOW confidence)
- [Chrome Community: --autoplay-policy flag not respected](https://support.google.com/chrome/thread/207847413/) - needs validation on actual Chrome version used in kiosk

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all browser-native APIs; no third-party libraries needed; verified via MDN official docs
- Architecture: HIGH - CSS z-index stacking is well-documented; `onended` event behavior confirmed; single-element reuse pattern is W3C recommended
- Pitfalls: HIGH - all 6 pitfalls traced to MDN specs, Chromium bug tracker, or existing project research (PITFALLS.md)
- Video sequence: HIGH - exact sequence extracted from `controller.py` source code (ground truth)

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain -- HTML5 video APIs are mature)
