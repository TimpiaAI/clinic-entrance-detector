# Pitfalls Research

**Domain:** Clinic kiosk web platform — MJPEG streaming, Web Audio API, Python subprocess management, sleep prevention, kiosk-mode browser
**Researched:** 2026-03-05
**Confidence:** HIGH (all critical pitfalls verified against official docs, browser bug trackers, and authoritative community sources)

---

## Critical Pitfalls

### Pitfall 1: MJPEG `<img>` Tag Causes Memory Exhaustion

**What goes wrong:**
Rendering the MJPEG detection feed via a plain `<img src="http://localhost:8080/video_feed">` tag causes the browser to accumulate frames in memory and never release them. On a mini PC running 24/7, this produces a slow leak that eventually OOMs the tab or the OS. Firefox historically exhausted all RAM this way. Chromium handles it better but still degrades over hours at 1280x720 and 15 FPS.

**Why it happens:**
The browser's image decoder was designed for static images. When fed a multipart MJPEG stream, it may buffer all decoded frames or fail to release older ones promptly. The browser treats the stream as an "animated image" and falls back to rendering only the first frame in some contexts, or degrades to a CPU-burning decode loop.

**How to avoid:**
Use a `fetch()` ReadableStream loop that reads the MJPEG multipart boundary, extracts JPEG blobs, creates object URLs, draws them to a `<canvas>`, and immediately calls `URL.revokeObjectURL()` after each draw. This gives explicit memory control. Alternatively, use `<img>` with a JavaScript watchdog that periodically resets `src` to force a fresh connection. The fetch-to-canvas pattern is strictly preferred.

```js
// Correct pattern: fetch loop → canvas, explicit URL revocation
async function startMjpegStream(url, canvas) {
  const ctx = canvas.getContext('2d');
  const response = await fetch(url);
  const reader = response.body.getReader();
  // ... parse multipart/x-mixed-replace boundary, extract JPEG chunks
  // for each frame:
  //   const blob = new Blob([frameBytes], { type: 'image/jpeg' });
  //   const blobUrl = URL.createObjectURL(blob);
  //   const img = new Image();
  //   img.onload = () => { ctx.drawImage(img, ...); URL.revokeObjectURL(blobUrl); };
  //   img.src = blobUrl;
}
```

**Warning signs:**
- Chrome Task Manager shows tab memory growing monotonically
- Browser becomes sluggish after 2-4 hours
- CPU usage climbs even when detection is idle

**Phase to address:** Video feed phase (MJPEG rendering). Must be implemented correctly from day one — retrofitting is disruptive.

---

### Pitfall 2: HTML5 Video Autoplay Silently Fails Unless Muted

**What goes wrong:**
`videoElement.play()` returns a Promise that rejects if autoplay is blocked. If the rejection is not caught, nothing visible happens — the instructional video does not start, the patient gets a frozen screen, and the workflow stalls. The instructional videos have audio (instructions in Romanian), so they cannot simply be muted permanently.

**Why it happens:**
Chrome's autoplay policy requires either: (a) the video is muted, or (b) the user has interacted with the page (click, keypress) before playback starts. A kiosk that has been idle since boot may have lost its "user interaction" state. The `--autoplay-policy=no-user-gesture-required` command-line flag is the correct production fix but is often forgotten.

**How to avoid:**
Two-part fix:
1. Always `await video.play()` and catch the rejection, logging the error and re-attempting after the next user gesture.
2. For kiosk production launch, add `--autoplay-policy=no-user-gesture-required` to the Chrome startup flags.

```js
// Correct: always handle play() promise
try {
  await videoElement.play();
} catch (err) {
  console.error('Autoplay blocked:', err);
  // Queue for retry after next user interaction
}
```

**Warning signs:**
- Console errors: "NotAllowedError: play() failed because the user didn't interact with the document first"
- Video element frozen on first frame
- Workflow advances but no audio/video is heard/seen

**Phase to address:** Video playback phase. Add the Chrome flag to the kiosk launch script at the same time as `--kiosk`.

---

### Pitfall 3: Web Audio API `AudioContext` Starts in Suspended State

**What goes wrong:**
`new AudioContext()` created on page load is silently put into `suspended` state by Chrome. Calling `getUserMedia()` and starting MediaRecorder works without errors, but the audio graph does not process. The recording appears to succeed, sending silent or empty audio chunks to the Faster Whisper backend, which returns an empty transcript. The operator sees the system "working" but the CNP is never extracted.

**Why it happens:**
Chrome's autoplay policy applies to AudioContext too. A context created before any user interaction is suspended and requires an explicit `audioContext.resume()` call inside a user gesture event handler to move to `running`.

**How to avoid:**
Create the `AudioContext` lazily — inside the same button-click or keyboard-shortcut handler that starts the recording session. If the context must be created early, attach a one-time listener to the activation keyboard shortcut (`Start` system toggle) that calls `audioContext.resume()`.

```js
// Correct: create/resume AudioContext only inside user gesture
startButton.addEventListener('click', async () => {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  } else if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }
  // ... start getUserMedia and recording
});
```

**Warning signs:**
- `audioContext.state` is `'suspended'` after creation
- Console warning: "The AudioContext was not allowed to start"
- MediaRecorder fires `ondataavailable` but chunks contain silence
- Whisper returns empty or near-empty transcription

**Phase to address:** Audio recording phase. Validate `audioCtx.state === 'running'` before starting any recording flow.

---

### Pitfall 4: `getUserMedia()` Fails Silently Outside Secure Context

**What goes wrong:**
`navigator.mediaDevices` is `undefined` when the page is served over plain HTTP from any origin other than `localhost` / `127.0.0.1`. In production, if the mini PC is accessed by hostname (e.g., `http://clinic-kiosk/`) rather than `localhost`, the microphone API is completely unavailable. The error is a JavaScript TypeError on `undefined.getUserMedia`, not a meaningful permission error.

**Why it happens:**
Chrome and all modern browsers restrict `getUserMedia` to secure contexts (HTTPS or `localhost`) since Chrome 74. Serving via hostname over plain HTTP silently removes the API.

**How to avoid:**
Always serve the frontend from `http://localhost:PORT` or over HTTPS. In the kiosk launch script, use `http://localhost:3000` as the startup URL, never the machine hostname. Add an explicit startup check:

```js
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
  showFatalError('Microfon indisponibil: pagina necesita HTTPS sau localhost.');
  return;
}
```

**Warning signs:**
- `navigator.mediaDevices` is `undefined`
- Page loads without error but mic recording silently never initializes
- Only reproducible when accessed via machine hostname, not localhost

**Phase to address:** Audio recording phase, but the URL convention must be locked down in the kiosk launch script during the kiosk hardening phase.

---

### Pitfall 5: Python Subprocess Leaves Zombie / Orphan Processes on Windows

**What goes wrong:**
Calling `subprocess.Popen` to start the detector, then `process.terminate()` to stop it, does not reliably kill the entire process tree on Windows. The YOLOv8 + OpenCV pipeline spawns child workers; `terminate()` kills only the top-level Python process. The children (OpenCV threads, BoT-SORT workers) keep running, holding the webcam device. The next time the operator clicks "Start", the new detector fails because the camera is already open.

**Why it happens:**
Windows does not support POSIX signals. `process.terminate()` sends `SIGTERM` which is an alias for `kill()` on Windows — but it only kills the root process, not descendants. `SIGKILL` does not exist on Windows.

**How to avoid:**
Use `psutil` to walk and kill the entire process tree, with a graceful-then-force pattern:

```python
import psutil, subprocess, signal

def kill_process_tree(pid: int):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs([parent] + children, timeout=3)
        for p in alive:
            p.kill()
    except psutil.NoSuchProcess:
        pass
```

As a fallback, `subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)])` works on Windows without psutil.

**Warning signs:**
- "Camera already in use" error on second "Start" click
- Task Manager shows multiple python.exe processes after "Stop"
- Detector fails to initialize on the second launch

**Phase to address:** Process management phase. Test the full start/stop cycle at least 5 times in a row during development.

---

### Pitfall 6: Screen Wake Lock Silently Released, System Sleeps Mid-Session

**What goes wrong:**
`navigator.wakeLock.request('screen')` succeeds, but the wake lock is automatically released when the tab loses visibility (user presses Alt+Tab, or Windows switches context for any reason). After the lock releases, the OS sleep timer resumes. If the clinic PC is configured to sleep after 5 minutes, the screen goes dark mid-session with a patient present.

**Why it happens:**
The Screen Wake Lock API spec mandates automatic release when `document.visibilityState` changes to `'hidden'`. This is correct browser behavior but fatal in a kiosk that must stay awake indefinitely.

**How to avoid:**
Two-layer approach:
1. **Browser layer:** Listen for `visibilitychange` and re-request the wake lock when the document becomes visible again. This handles tab switches.
2. **OS layer:** Have the FastAPI backend call `powercfg /change monitor-timeout-ac 0` (Windows) or `caffeinate -d` (macOS) when the system is activated. The OS-level prevention is the real defense; the browser wake lock is a belt-and-suspenders fallback.

```js
let wakeLock = null;

async function requestWakeLock() {
  try {
    wakeLock = await navigator.wakeLock.request('screen');
  } catch (err) {
    console.warn('Wake lock not granted:', err);
  }
}

document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible') {
    await requestWakeLock();
  }
});
```

**Warning signs:**
- `wakeLock.released` becomes `true` without an explicit call to `release()`
- System goes to sleep after `visibilityState` momentarily changes to `'hidden'`
- Wake lock acquisition fails (low battery, user policy) — no error is surfaced to the user

**Phase to address:** Sleep prevention phase. Both layers must be implemented together; the browser-only approach is insufficient for 24/7 kiosk use.

---

### Pitfall 7: Chrome Kiosk Mode Keyboard Escape Routes

**What goes wrong:**
`--kiosk` mode prevents F11 toggling, right-click context menus, and address bar access, but several keyboard combinations remain active and can expose the OS to a patient or unsophisticated operator:
- `Alt + F4` — closes Chrome entirely
- `Shift + Esc` — opens Chrome's Task Manager (a process killer)
- `Ctrl + J` — opens Chrome Downloads panel
- `F12` / `Ctrl + Shift + I` — opens DevTools

On Windows 10/11, swipe gestures from screen edges activate Action Center, Task View, and the taskbar even when Chrome is fullscreen.

**Why it happens:**
`--kiosk` is a display mode, not a security lockdown. Chrome does not intercept OS-level key combinations.

**How to avoid:**
Three layers of mitigation:
1. **JavaScript:** Listen for `keydown` and intercept `F12`, `Ctrl+J`, `Ctrl+Shift+I`, and other known Chrome shortcuts, calling `event.preventDefault()`. You cannot intercept `Alt+F4` from JavaScript (OS-level), so address it at the OS level.
2. **OS Group Policy (Windows):** Disable `Alt+F4` for the kiosk user via Local Group Policy Editor or use a kiosk account type.
3. **Launch flags:** Add `--disable-dev-tools`, `--no-first-run`, `--noerrdialogs`, `--disable-infobars` to the Chrome launch command.

For production, setting up a dedicated Windows kiosk account (Settings → Accounts → Assigned Access) handles the OS-level restrictions automatically.

**Warning signs:**
- Operator can open Task Manager via Shift+Esc
- Chrome shows "Restore pages" dialog after unexpected close (add `--disable-session-crashed-bubble`)
- DevTools opens on F12 keypress

**Phase to address:** Kiosk hardening phase, after core functionality is working.

---

### Pitfall 8: MediaRecorder Chunk Format Incompatible with Faster Whisper

**What goes wrong:**
`MediaRecorder` defaults to `audio/webm;codecs=opus` on Chrome. The Faster Whisper Python backend expects audio files it can feed to ffmpeg or load via `librosa`/`soundfile`. Passing raw WebM/Opus chunks directly to `whisper.transcribe()` fails or produces garbage — only the first chunk contains a valid WebM header, subsequent chunks are headerless and undecodable as standalone files.

**Why it happens:**
WebM is a container format. When `MediaRecorder` time-slices the recording (e.g., 1-second chunks), each `ondataavailable` event produces a fragment of the container. Only the first fragment has the initialization cluster (header). Individual chunks are not valid standalone audio files.

**How to avoid:**
Two viable approaches:
1. **Accumulate then transcribe:** Record the entire utterance as one blob (stop the recorder, use the final `ondataavailable` blob), send as a complete WebM file. This produces a valid, decodable file.
2. **Convert in browser:** Use `AudioContext.decodeAudioData()` to get raw PCM, encode as WAV (16-bit, 16kHz mono) in JavaScript, send WAV. WAV is trivially decodable by Whisper/ffmpeg.

The WAV approach is preferred because 16kHz mono WAV is Whisper's native input format, eliminating any format conversion latency on the backend.

```js
// Correct: convert to WAV before sending
const pcmBuffer = await audioCtx.decodeAudioData(webmArrayBuffer);
const wavBlob = pcmToWav(pcmBuffer, 16000); // custom encoder
await fetch('/api/transcribe', { method: 'POST', body: wavBlob });
```

**Warning signs:**
- Whisper returns empty string for all recordings
- Backend logs show ffmpeg decode errors on chunks
- Works when sending one long recording but fails when chunks are sent individually

**Phase to address:** Audio pipeline phase. Define the audio format contract (16kHz mono WAV) before building the recording and transcription endpoints.

---

### Pitfall 9: WebSocket Silently Disconnects Due to Browser Power-Saving

**What goes wrong:**
The WebSocket connection to FastAPI (`/ws/state`) is used for real-time detection status updates (FPS, active tracks, entry events). When Chrome is in the background or when Windows power-saving throttles background tabs, the JavaScript event loop slows to approximately once per minute. The WebSocket keepalive heartbeat fails, the connection closes silently, and the `onclose` event may not fire promptly. The frontend shows stale state (last FPS reading frozen) while the detector continues running.

**Why it happens:**
Chrome throttles background tab timers to 1Hz when the tab is backgrounded. Browser-side ping/pong timers fire once per minute instead of every 30 seconds. FastAPI's WebSocket `ping_interval` may expire before the browser responds, closing the connection server-side.

**How to avoid:**
Implement exponential-backoff reconnection on the client. The WebSocket wrapper must:
1. Detect `onclose` / `onerror`
2. Attempt reconnection with backoff (0.5s → 1s → 2s → ... → 30s cap)
3. On reconnection, request a full state snapshot to re-sync UI

Keep the tab visible (kiosk mode ensures this). The backend should configure `ping_interval=20, ping_timeout=10` on the Starlette WebSocket to detect dead connections promptly.

**Warning signs:**
- FPS counter freezes while detection is running
- Entry events stop appearing in the log table
- Console shows WebSocket close code 1006 (abnormal closure)

**Phase to address:** Real-time state phase. Reconnection logic should be built into the WebSocket client abstraction from the start.

---

### Pitfall 10: Vite Dev Proxy Silently Drops WebSocket Upgrades

**What goes wrong:**
During development, Vite proxies HTTP requests from port 3000 to FastAPI on port 8080. HTTP proxying works. WebSocket connections fail with "WebSocket connection failed" or silently fall back to polling, because Vite's proxy does not forward WebSocket upgrades by default.

**Why it happens:**
Vite's proxy configuration requires explicit `ws: true` to enable WebSocket proxying. Without it, the `Connection: Upgrade` header is stripped and the WebSocket handshake fails.

**How to avoid:**
Add `ws: true` to every WebSocket proxy entry in `vite.config.js`:

```js
// vite.config.js
export default {
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8080',  ws: true },
    }
  }
}
```

Also ensure FastAPI's CORS middleware allows `localhost:3000` during development, or CORS preflight will block API calls before the proxy even gets them.

**Warning signs:**
- HTTP API calls work but WebSocket connections throw errors
- Browser Network tab shows WebSocket connection immediately failing (101 Upgrade never returned)
- The issue only reproduces in Vite dev mode, not in production build

**Phase to address:** Frontend setup phase (day one of Vite configuration). Catch this in the first integration test of the WebSocket feed.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `<img>` tag for MJPEG | Zero code, works immediately | Memory leak after hours; browser freeze | Never for 24/7 kiosk |
| Hard-code `http://localhost:8080` in frontend | Simple | Breaks if backend port changes; no env config | MVP only — move to `import.meta.env.VITE_API_URL` before production |
| `audioContext.state` not checked before recording | Fewer code paths | Silent empty recordings; confusing transcription failures | Never — always check state |
| `process.terminate()` without psutil tree kill | Simple | Camera lock on Windows after stop/start | Never on Windows target |
| Browser Wake Lock only (no OS-level prevention) | No backend changes needed | System sleeps in edge cases (low battery policy, user GPU driver policy) | Never for 24/7 kiosk |
| `--autoplay-policy=no-user-gesture-required` only (no error handling in JS) | Works in kiosk | Fails silently in dev mode without the flag | Acceptable for production builds only |
| Send WebM chunks directly to Whisper | Simple recording loop | Chunk format incompatibility, silent transcription failures | Never |
| No WebSocket reconnection | Simpler initial code | Stale UI state after any network hiccup or tab background | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| MJPEG stream → browser | Use `<img src>` pointing at stream URL | Fetch loop with multipart boundary parser, draw to canvas, revoke object URLs |
| Vite dev → FastAPI WebSocket | Proxy only HTTP, forget `ws: true` | Add `ws: true` in vite.config proxy for all `/ws/*` paths |
| MediaRecorder → Faster Whisper | Send raw WebM chunks as individual audio files | Accumulate full recording or convert to 16kHz mono WAV before POSTing |
| `getUserMedia` → kiosk | Expect browser prompt at runtime in kiosk mode | Use `--use-fake-ui-for-media-stream` flag to auto-grant, verify on `localhost` |
| `subprocess.Popen` → Windows | `process.terminate()` leaves children running | Use psutil tree kill or `taskkill /F /T /PID` |
| Sleep prevention | Browser Wake Lock only | Wake Lock + OS-level `powercfg`/`caffeinate` via FastAPI backend command |
| HTML5 `video.play()` → kiosk | Assume it works, no error handling | `await play()` with catch; `--autoplay-policy=no-user-gesture-required` in launch script |
| AudioContext → recording | Create at module load | Create lazily inside user gesture handler, check `.state === 'running'` before use |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| MJPEG `<img>` tag (no object URL revocation) | Memory grows ~50MB/hour at 15 FPS, 720p | Fetch-to-canvas with explicit `URL.revokeObjectURL()` | After 2-4 hours continuous operation |
| Drawing MJPEG canvas in main thread with heavy DOM updates simultaneously | Frame drops, choppy video during entry events | Use `requestAnimationFrame` for canvas draws, decouple from DOM update cycle | When entry event log table has >50 rows being updated |
| MediaRecorder with very short `timeslice` (< 250ms) | Huge chunk count, dropped first-chunk headers, unparseable audio | Use 1-3 second timeslice or no timeslice (stop-and-collect pattern) | Always — per-chunk format issues are constant |
| Re-creating `AudioContext` on every recording | Subtle latency, resource leak, eventual browser audio subsystem failure | Create once, reuse across recordings, only resume/suspend as needed | After ~20 recordings in one session |
| Polling FastAPI `/status` endpoint instead of WebSocket | Extra HTTP connections, 100ms+ state lag, extra server load | Use existing WebSocket stream for all state updates | After ~5 concurrent polling intervals |

---

## Security Mistakes

This system runs on a local network with no authentication, but still has relevant security considerations:

| Mistake | Risk | Prevention |
|---------|------|------------|
| Expose FastAPI on `0.0.0.0` with process management endpoints | Any device on clinic LAN can start/stop the detector or kill processes | Bind to `127.0.0.1` only; all frontend access goes through `localhost` |
| Log CNP/email data to browser console | Patient PII visible in kiosk DevTools if accessible | Never `console.log` CNP or email; log as masked values (e.g., `CNP: ****1234`) |
| Store patient data (CNP/email) in localStorage | Persists indefinitely on kiosk; next patient or service tech can read prior data | Keep all captured patient data in JavaScript memory only; clear on workflow completion/timeout |
| `--disable-web-security` Chrome flag for CORS bypass | Disables all browser same-origin protections | Fix CORS in FastAPI middleware; never use this flag |
| Run detector as administrator/root to access camera | Unnecessary privilege escalation | Regular user account with camera permission is sufficient on both Windows and macOS |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Instructional video plays with no visible loading state | Patient sees blank screen for 1-2s while video loads, thinks system is broken | Show a spinner overlay that disappears on `video.canplaythrough` event |
| No visible indication recording is active | Patient doesn't know when to speak | Show pulsing microphone indicator + recording timer during capture window |
| "System error" in English on a Romanian-only kiosk | Operator/patient confused | All error messages in Romanian, including JavaScript error boundaries |
| Entry event beep/notification while video is playing | Interrupts instructional video with unexpected audio | Suppress entry audio notifications during active video playback state |
| Kiosk shows browser "Restore session" dialog after power outage | Patient or staff sees unexpected Chrome dialog, cannot dismiss without mouse | Add `--disable-session-crashed-bubble` and `--noerrdialogs` to kiosk launch script |
| Entry log table grows indefinitely | After 8+ hours, DOM has thousands of rows; page becomes slow | Cap displayed entries at 100; use virtual scrolling or auto-prune on backend query |

---

## "Looks Done But Isn't" Checklist

- [ ] **MJPEG stream:** Works in 30-minute demo — verify no memory growth over 4 hours with Chrome Task Manager open
- [ ] **Video autoplay:** Works when you click a button before testing — verify it works with `--kiosk` flag and no prior user interaction (cold boot scenario)
- [ ] **Microphone recording:** `ondataavailable` fires and chunks are non-empty — verify Whisper transcription actually works end-to-end with the WebM/WAV format being sent
- [ ] **Sleep prevention:** Wake Lock granted initially — verify the screen stays on after 10+ minutes of inactivity with no interaction (mimics overnight idle)
- [ ] **Process management:** Start/stop works once — verify the cycle works 5 consecutive times without camera lock errors
- [ ] **Kiosk escape prevention:** Looks locked — verify `Shift+Esc`, `Ctrl+J`, `F12` are all intercepted
- [ ] **WebSocket state feed:** Shows live data — verify it reconnects automatically after `kill -9 uvicorn` and restart
- [ ] **Windows vs macOS:** Works on macOS dev — run the full workflow on Windows 11 before declaring done; path separators, signal handling, and audio device names all differ
- [ ] **Entry log:** Shows current entries — verify DOM performance after 200 entries are added rapidly

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| MJPEG memory leak already in production | HIGH | Refactor `<img>` to fetch-to-canvas — affects the core video rendering component; test thoroughly |
| AudioContext silently suspended — missed this | MEDIUM | Add state check + resume call at recording start; requires one-line fix but needs full audio pipeline retest |
| WebM chunks sent to Whisper — transcription broken | MEDIUM | Switch to stop-and-collect + WAV conversion; impacts the audio → backend API contract |
| Zombie processes on Windows — camera stuck | MEDIUM | Add psutil tree kill; Windows-specific code path; test 5x start/stop cycles |
| Kiosk escape routes discovered post-deployment | LOW | Add JS keydown interceptors + Chrome flags to launch script; no frontend code changes needed |
| Wake lock not re-acquired after visibility change | LOW | Add one `visibilitychange` listener with `requestWakeLock()` call |
| Video autoplay blocked on first kiosk boot | LOW | Add `--autoplay-policy=no-user-gesture-required` to Chrome launch script |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| MJPEG memory leak (img tag) | Video feed phase | Chrome Task Manager shows stable memory over 1 hour; `URL.revokeObjectURL` visible in code |
| HTML5 video autoplay blocked | Video playback phase | Test cold-boot kiosk launch with no prior user interaction; check `video.play()` catch handler present |
| AudioContext suspended | Audio recording phase | `audioCtx.state === 'running'` checked before every recording start |
| getUserMedia outside secure context | Frontend setup phase | Explicit `navigator.mediaDevices` guard in initialization code |
| Python subprocess zombie on Windows | Process management phase | 5x start/stop cycle on Windows without camera lock; psutil in requirements |
| Wake lock released on visibility change | Sleep prevention phase | `visibilitychange` listener present; verified with 10-minute idle test |
| Kiosk keyboard escape routes | Kiosk hardening phase | Manual test of `Shift+Esc`, `Ctrl+J`, `F12`, `Alt+F4` on kiosk account |
| MediaRecorder WebM chunk format | Audio pipeline phase | Whisper transcription test with actual frontend-generated audio, not hand-crafted test files |
| WebSocket silent disconnect | Real-time state phase | Kill uvicorn mid-session; frontend reconnects and re-displays live data within 30s |
| Vite WebSocket proxy misconfiguration | Frontend setup phase | WebSocket connection works in Vite dev mode before any other feature is built |

---

## Preserved Pitfalls from Previous Architecture (Still Relevant)

The following pitfalls from the prior Python-only system remain relevant for the web platform:

### Whisper Transcription Speed on Target Hardware
**What goes wrong:** Faster Whisper medium model can take 30-60 seconds on a mini PC under load.
**Prevention:** Benchmark on the Windows 11 mini PC. Use `small` model + int8 if latency is unacceptable. The web UI must show a loading state during transcription — the patient cannot stare at a blank screen.

### Workflow Timeout / Patient Abandonment
**What goes wrong:** No timeout → system stuck waiting for speech forever.
**Prevention:** Implement frontend state machine with a countdown timer (e.g., 30 seconds for speech capture). On timeout, return to idle video, clear captured data. The frontend timer drives this, not just the backend.

### CNP/Email Transcription Reliability
**What goes wrong:** Whisper outputs words instead of digits; email addresses frequently wrong.
**Prevention:** Show transcribed text to the patient with a visual confirmation step. Romanian: "Am înțeles: [CNP]. Este corect?" with keyboard shortcut to confirm or retry.

### Video File Path at Runtime
**What goes wrong:** Relative paths break when working directory differs (systemd service).
**Prevention:** Backend serves video files from an absolute path configured in the `.env`; frontend requests videos via the API URL, never direct file paths.

---

## Sources

- Firefox MJPEG memory leak bug: https://bugzilla.mozilla.org/show_bug.cgi?id=662195
- Firefox MJPEG frame drop bug: https://bugzilla.mozilla.org/show_bug.cgi?id=1280351
- MJPEG stream TCP not closed on navigation: https://bugzilla.mozilla.org/show_bug.cgi?id=915755
- Chrome autoplay policy: https://developer.chrome.com/blog/autoplay
- Web Audio API best practices (MDN): https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices
- AudioContext suspended state: https://github.com/WebAudio/web-audio-api/discussions/2604
- getUserMedia secure context requirement: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- Screen Wake Lock API (MDN): https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API
- Wake Lock auto-release on visibility change: https://developer.chrome.com/docs/capabilities/web-apis/wake-lock
- Chrome kiosk mode guide: https://smartupworld.com/chromium-kiosk-mode/
- Chrome kiosk mode keyboard shortcuts: https://www.labs.bristolmuseums.org.uk/running-google-chrome-in-kiosk-mode-tips-tricks-and-workarounds/
- psutil process tree kill: https://psutil.readthedocs.io/en/latest/
- Python subprocess zombie prevention: https://dev.to/generatecodedev/how-to-safely-kill-python-subprocesses-without-zombies-3h9g
- FastAPI subprocess signal handling: https://github.com/fastapi/fastapi/discussions/7442
- MediaRecorder chunk format issue: https://github.com/chrisguttandin/extendable-media-recorder/issues/638
- MediaRecorder huge chunks: https://blog.addpipe.com/dealing-with-huge-mediarecorder-slices/
- WebSocket browser power-saving disconnects: https://www.pixelstech.net/article/1719122489-the-pitfall-of-websocket-disconnections-caused-by-browser-power-saving-mechanisms
- Vite WebSocket proxy `ws: true` bug: https://github.com/vitejs/vite/issues/20223
- MJPEG stream 30-minute timeout: https://community.netcamstudio.com/t/mjpeg-stream-stops-after-30-minutes-timeout-use-web-api-to-reload-page-and-stream/2813
- `--use-fake-ui-for-media-stream` flag: https://blog.addpipe.com/getusermedia-getting-started/
- Windows sleep prevention powercfg: https://gist.github.com/scivision/d0e6dbebb88687791129ad722c90e68a

---
*Pitfalls research for: Clinic kiosk web platform (MJPEG streaming, Web Audio API, Python process management, sleep prevention, kiosk-mode browser)*
*Researched: 2026-03-05*
