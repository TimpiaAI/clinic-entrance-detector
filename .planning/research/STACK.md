# Technology Stack

**Project:** Clinic Entrance Kiosk — Web Platform (Milestone 2)
**Domain:** Kiosk web app with real-time video feeds, HTML5 video playback, Web Audio recording, WebSocket communication
**Researched:** 2026-03-05
**Confidence:** HIGH (verified via official docs, MDN, Vite docs, PyPI)

---

## Context: What This Milestone Adds

The existing system has a working Python/FastAPI backend (port 8080) with:
- MJPEG stream at `/video_feed`
- WebSocket state updates at `/ws`
- Calibration REST API at `/api/calibration`
- Faster Whisper v1.2.1 for Romanian STT (existing in controller.py)
- 8 x video1-8.mp4 on disk

This milestone replaces:
- VLC RC socket controller (fragile) → HTML5 `<video>` in browser
- Flask controller (port 5050) → FastAPI endpoint (same port 8080)
- `sounddevice` mic capture → Web Audio API in browser
- Jinja2 dashboard templates → Vite-built static frontend

---

## Recommended Stack

### Frontend Core

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Vite | 7.x (`^7.3.1`) | Build tool and dev server | Current stable (confirmed npm). Native ESM, instant HMR, `vanilla-ts` template is zero-framework. Rollup-based production build. No overhead from React/Vue runtime. Required: Node.js 20.19+ or 22.12+. |
| TypeScript | 5.x (bundled with Vite) | Type safety | `vanilla-ts` template includes it for free. Catches API shape mismatches at compile time — critical when consuming FastAPI JSON. Transpiled by esbuild (20-30x faster than tsc). |
| Vanilla JS/TS | — | No UI framework | This is a single-screen kiosk app with ~5 DOM elements. React/Vue add 40-80KB runtime and conceptual overhead for zero gain. Direct DOM manipulation is the correct choice. |

### Frontend Media APIs (browser-native, no libraries)

| API | Browser Support | Purpose | Implementation Notes |
|-----|----------------|---------|----------------------|
| `<img src="...">` MJPEG | All modern browsers | Display MJPEG detection feed | Set `<img>` `src` to `http://localhost:8080/video_feed`. Browser handles multipart MJPEG natively. No JS needed. Confirmed working with FastAPI `StreamingResponse`. |
| `<video>` HTML5 | Universal | Instructional video playback (video1-8.mp4) | `preload="auto"` on all 8 videos at startup. Overlay via CSS `position: absolute` on same container as MJPEG img. `play()` / `pause()` / `load()` API. No external player needed. |
| `WebSocket` | Universal | Real-time state updates from backend | Native `new WebSocket('ws://...')`. Implement exponential backoff reconnect (1s base, 30s max, 2x multiplier, 10% jitter). Reset delay on connect. |
| `navigator.mediaDevices.getUserMedia` | Chrome 47+, all modern | Mic access for audio recording | Request `{audio: {sampleRate: 16000, channelCount: 1}}`. Requires HTTPS or localhost. |
| `MediaRecorder` | Chrome 47+, all modern | Chunked audio capture → backend | Use `timeslice: 3000` (3-second chunks). Check `MediaRecorder.isTypeSupported('audio/webm;codecs=opus')`. WebM/Opus is universally supported in Chrome and is accepted by faster-whisper (via ffmpeg). |
| `Screen Wake Lock API` | Chrome 84+, all modern browsers as of 2025 | Prevent screen sleep while active | `navigator.wakeLock.requestWakeLock('screen')`. 88% browser compatibility as of 2026. Requires secure context (HTTPS or localhost). Re-acquire on `visibilitychange` event (lock releases when tab is hidden). |

### Backend Additions (extend existing FastAPI)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | `>=0.109.0` (already installed) | Extend: serve static files, add /api/transcribe, /api/process/start-stop, /api/video/:id | Already in use. `StaticFiles` mounts Vite dist output. `UploadFile` receives audio blobs. Zero new framework needed. |
| python-multipart | `>=0.0.6` (already installed) | Parse multipart audio uploads from browser | `UploadFile` in FastAPI requires this. Already in requirements.txt. |
| faster-whisper | `1.2.1` (already installed) | Romanian STT transcription of browser audio | Latest stable (PyPI, October 2025). Accepts WebM/Opus from MediaRecorder via ffmpeg. model=`medium`, compute_type=`int8`. |
| wakepy | `1.0.0` | Backend-side sleep prevention on Windows 11 and macOS | Cross-platform, no admin rights needed. `keep.presenting` mode prevents sleep + screen off + screensaver. Wraps `caffeinate` on macOS, `SetThreadExecutionState` on Windows. Use as context manager around system active state. Fallback if Screen Wake Lock API is blocked by OS policy. |
| aiofiles | `>=23.2.0` | Async file reads for serving video files if needed | FastAPI `StaticFiles` handles this, but needed if video files are served via custom route with range requests. |

### Development Tooling

| Tool | Purpose | Notes |
|------|---------|-------|
| Vite dev proxy | Forward `/api/*` and `/ws` to FastAPI on port 8080 during development | Configure in `vite.config.ts`: `server.proxy` with `ws: true` for WebSocket proxying. Eliminates CORS issues in dev. Not needed in production (same origin). |
| TypeScript strict mode | Catch shape mismatches at compile time | `"strict": true` in tsconfig.json. Use interface types for WebSocket payloads matching FastAPI `DashboardState.snapshot()`. |
| ESLint | Code quality | Include in `vanilla-ts` scaffold. Minimal config. |

---

## Installation

```bash
# Frontend scaffold (run once in project root)
npm create vite@latest frontend -- --template vanilla-ts
cd frontend
npm install

# No additional npm packages needed — all APIs are browser-native

# Backend additions (Python)
pip install wakepy aiofiles
# faster-whisper and python-multipart already installed
```

---

## Configuration

### Vite Dev Server Proxy (`frontend/vite.config.ts`)

```typescript
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
        changeOrigin: true,
      },
      '/video_feed': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    }
  },
  build: {
    outDir: '../frontend_dist',  // FastAPI serves from here
  }
})
```

### FastAPI Static File Serving (production)

```python
from fastapi.staticfiles import StaticFiles

# Mount built frontend — add after all API routes
app.mount("/", StaticFiles(directory="frontend_dist", html=True), name="frontend")
```

### Chrome Kiosk Launch

```bash
# Windows (production)
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --kiosk http://localhost:8080 ^
  --no-first-run ^
  --disable-session-crashed-bubble ^
  --disable-infobars ^
  --noerrdialogs ^
  --user-data-dir=%TEMP%\clinic-kiosk-profile

# macOS (development)
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --kiosk http://localhost:8080 \
  --no-first-run \
  --disable-session-crashed-bubble \
  --user-data-dir=/tmp/clinic-kiosk-profile
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Frontend framework | Vite + vanilla TS | React + Vite | React adds ~45KB runtime, JSX compilation, hook rules, and conceptual overhead for a single-screen kiosk with 5 DOM elements. Zero benefit. |
| Frontend framework | Vite + vanilla TS | Vue 3 + Vite | Lighter than React but still 20KB runtime, Options/Composition API choice, single-file-component complexity. Overkill for this scope. |
| MJPEG display | Native `<img>` tag | Fetch + ReadableStream parser | MJPEG `<img>` works natively in all Chromium-based browsers. ReadableStream approach is only needed if you need per-frame processing (e.g., canvas overlay). The backend already renders overlays in OpenCV — no need to parse frames in JS. |
| Audio capture | `MediaRecorder` (WebM/Opus) | `AudioWorklet` + PCM streaming | AudioWorklet produces raw PCM (16-bit mono) which is ideal for Whisper. However, it requires more code (custom AudioWorkletProcessor), binary WebSocket frames, and a custom receiver. MediaRecorder WebM/Opus chunks are simpler, fully supported, and faster-whisper accepts them via ffmpeg. Use AudioWorklet only if latency < 1s is required (it is not for this use case — patient speaks, waits ~3-4 seconds for transcription). |
| Audio capture | `MediaRecorder` (WebM/Opus) | `getUserMedia` + `sounddevice` (Python) | sounddevice requires physical mic to be managed by the server process, not the browser. Creates a platform dependency and conflicts with browser mic permissions. Browser-based capture is the correct architecture for kiosk. |
| Sleep prevention | `Screen Wake Lock API` + `wakepy` | `powercfg` subprocess / registry editing | powercfg requires admin rights and is a global system change. Screen Wake Lock is the correct web-standard approach. wakepy provides a Python-side fallback using OS-level APIs without admin rights. |
| Sleep prevention | `Screen Wake Lock API` | Chrome `Keep Awake` extension | Browser extensions are blocked in `--kiosk` mode. Not viable. |
| Video serving | `StaticFiles` in FastAPI | Separate nginx server | nginx adds operational complexity for a local single-machine deployment. FastAPI `StaticFiles` is sufficient for serving 8 pre-loaded .mp4 files from local disk. |
| Kiosk launcher | Chrome `--kiosk` flag | Electron | Electron is 150-200MB, requires its own Node.js runtime, and adds an entire separate application to deploy and maintain. Chrome is already installed on the clinic PC. |
| Kiosk launcher | Chrome `--kiosk` flag | Firefox kiosk mode | Firefox has `--kiosk` but Screen Wake Lock API was added later and has inconsistent behavior on Windows compared to Chrome. Stick with Chrome. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React / Vue / Angular | Runtime overhead for a single-screen kiosk with no routing, no component tree, no state management library needed. Adds build complexity for zero DX benefit. | Vite + vanilla TypeScript |
| Socket.IO | Adds a JS library and requires a compatible Python server. The backend already exposes a plain WebSocket at `/ws`. Socket.IO's reconnection logic is its main value — replicate that with 30 lines of vanilla JS instead. | Native `WebSocket` with exponential backoff |
| `keypress` event | Deprecated. Removed from Chrome 142+. Will break silently. | `keydown` with `event.code` |
| VLC / python-mpv | The entire point of this milestone is to replace VLC with HTML5 video. Do not re-introduce external video players. | HTML5 `<video>` element |
| `sounddevice` for browser audio | sounddevice binds to the OS audio device from Python. The browser also needs mic access. They will conflict. In a kiosk, the browser owns the mic. | `MediaRecorder` in browser → POST to `/api/transcribe` |
| Electron | 150-200MB runtime, separate deployment, update management. The app is already a website. | Chrome `--kiosk` flag |
| HTTPS in local dev / production | This is a local-only LAN deployment. HTTPS adds certificate management overhead. **Exception:** Screen Wake Lock API requires secure context — use `localhost` (which is treated as secure by Chrome) for both dev and production. | `http://localhost:8080` (localhost = secure context in Chrome) |
| npm libraries for WebSocket reconnect (e.g., `reconnecting-websocket`) | Adds 5KB of dependency for 30 lines of vanilla code. More importantly, a kiosk app should have zero unexpired transitive dependencies that could break on `npm audit`. | Inline exponential backoff reconnect class |

---

## Stack Patterns by Variant

**For development (macOS):**
- `npm run dev` → Vite dev server on port 5173
- Vite proxy forwards `/api`, `/ws`, `/video_feed` to FastAPI on port 8080
- Chrome launched normally (not `--kiosk`) for DevTools access
- Screen Wake Lock works on localhost in Chrome (secure context)

**For production (Windows 11 Pro):**
- `npm run build` → output to `frontend_dist/`
- FastAPI serves `frontend_dist/` via `StaticFiles` mount at `/`
- Chrome launched with `--kiosk http://localhost:8080`
- wakepy `keep.presenting` activated from FastAPI on system start
- No separate dev server, no proxy needed (same origin)

**If Screen Wake Lock is blocked by OS power policy:**
- wakepy backend fallback activates automatically
- Use `keep.presenting` context manager tied to detector lifecycle
- Log a warning in system status display

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Vite 7.x | Node.js 20.19+ or 22.12+ | Node 18 dropped in Vite 7. Check `node --version` on clinic mini PC. |
| faster-whisper 1.2.1 | Python 3.9+ | Clinic system uses Python 3.11+. Compatible. |
| wakepy 1.0.0 | Python 3.7-3.15, Windows XP+, macOS 10.8+ | No admin rights required on Windows 11 or macOS. |
| MediaRecorder audio/webm;codecs=opus | Chrome 49+, Edge 79+ | Confirmed supported. Always call `MediaRecorder.isTypeSupported()` before use. |
| Screen Wake Lock API | Chrome 84+, Edge 84+, Firefox 126+, Safari 16.4+ | 88% global browser support as of 2026. Works on localhost (treated as secure context). |
| FastAPI StaticFiles | fastapi >= 0.63.0, aiofiles installed | `aiofiles` is an implicit dependency for static file serving. Add explicitly. |

---

## Sources

- Vite official docs — https://vite.dev/guide/ — version 7.3.1, Node.js 20.19+ confirmed (HIGH confidence)
- Vite npm package — https://www.npmjs.com/package/vite — latest version verified
- MDN Screen Wake Lock API — https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API — browser support, HTTPS requirement (HIGH confidence)
- Chrome for Developers Wake Lock — https://developer.chrome.com/docs/capabilities/web-apis/wake-lock — Chrome 84+ confirmed
- web.dev Screen Wake Lock all browsers — https://web.dev/blog/screen-wake-lock-supported-in-all-browsers — all major browsers confirmed
- MDN MediaStream Recording API — https://developer.mozilla.org/en-US/docs/Web/API/MediaStream_Recording_API/Using_the_MediaStream_Recording_API (HIGH confidence)
- web.dev microphone recording — https://web.dev/patterns/media/microphone-record — getUserMedia best practices
- wakepy readthedocs 1.0.0 — https://wakepy.readthedocs.io/stable/ — keep.presenting mode, Windows/macOS confirmed (HIGH confidence)
- faster-whisper PyPI — https://pypi.org/project/faster-whisper/ — v1.2.1, October 2025 (HIGH confidence)
- FastAPI CORS — https://fastapi.tiangolo.com/tutorial/cors/ — CORSMiddleware configuration
- FastAPI StaticFiles — https://fastapi.tiangolo.com/tutorial/static-files/ — StaticFiles mount (HIGH confidence)
- Chromium kiosk flags — https://smartupworld.com/chromium-kiosk-mode/ — --kiosk, --noerrdialogs, --disable-infobars (MEDIUM confidence)
- Vite proxy WebSocket — https://vite.dev/config/server-options — ws: true confirmed
- WebSocket reconnect backoff — https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1 (MEDIUM confidence)
- whisper audio formats — https://github.com/openai/whisper/discussions/41 — WebM accepted via ffmpeg (MEDIUM confidence)

---

*Stack research for: Clinic Entrance Kiosk — Web Platform milestone*
*Researched: 2026-03-05*
