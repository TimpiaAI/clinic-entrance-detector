# Phase 2: Frontend Foundation - Research

**Researched:** 2026-03-05
**Domain:** Vite + vanilla TypeScript frontend -- MJPEG fetch-to-canvas, WebSocket real-time updates, keyboard shortcuts, Romanian UI
**Confidence:** HIGH

## Summary

Phase 2 scaffolds the entire Vite frontend and delivers three independently testable features: a live MJPEG camera feed rendered via fetch-to-canvas (not `<img>` tag), a real-time status panel and entry log driven by WebSocket, and keyboard shortcut bindings for operator control. The frontend directory does not yet exist -- this phase creates it from scratch using `npm create vite@latest frontend -- --template vanilla-ts`. No npm runtime dependencies are needed; all APIs (WebSocket, fetch ReadableStream, Canvas 2D, KeyboardEvent) are browser-native.

The single most critical technical decision in this phase is the MJPEG rendering approach. The existing dashboard uses `<img src="/video_feed">` which works for short sessions but leaks memory at 15 FPS / 720p and will crash the browser tab after 2-4 hours of continuous operation. The correct pattern for a 24/7 kiosk is fetch-to-canvas: use `fetch()` to get a ReadableStream, parse the multipart MJPEG boundary (`--frame\r\n`), extract JPEG blobs, create objectURLs, draw to canvas via `Image.onload`, and immediately call `URL.revokeObjectURL()`. The backend's boundary is `frame` (set in `dashboard/web.py` line 137: `b"--frame\r\n"`), and the Content-Type is `multipart/x-mixed-replace; boundary=frame`.

The second critical piece is the Vite dev proxy configuration. The WebSocket at `/ws` and the MJPEG stream at `/video_feed` must both be proxied to FastAPI on port 8080. The WebSocket proxy requires `ws: true` explicitly in `vite.config.ts` -- without it, the Connection: Upgrade header is stripped and WebSocket connections fail silently during development. This has been a documented Vite issue and must be configured on day one before any integration testing.

**Primary recommendation:** Implement the fetch-to-canvas MJPEG renderer as the first task after Vite scaffold. It is the foundation all other visual features build on and cannot be retrofitted without disrupting everything.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FEED-01 | Browser displays live MJPEG camera feed with bounding boxes, zones, and tripwire overlays | Fetch-to-canvas pattern with multipart boundary parser; overlays rendered server-side by OpenCV, no client-side overlay needed |
| FEED-02 | Operator can toggle detection overlay visibility on/off via keyboard shortcut | CSS opacity toggle on canvas element; MJPEG connection stays open; mapped to F3 via `event.code === "F3"` |
| FEED-03 | Entry log table shows detected entries with timestamp, person ID, confidence score, and snapshot thumbnail | WebSocket `event_log` array in snapshot payload; **snapshot field must be added to push_event in main.py** (currently missing from event_log entries) |
| FEED-04 | Status panel displays real-time metrics: FPS, active tracked people, total entries today, uptime, webhook status | All fields already in `DashboardState.snapshot()`: fps, current_people, entries_today, uptime_seconds, webhook_status, detector_running, wake_lock_active |
| FEED-05 | Entry log table updates in real-time via WebSocket (no page refresh needed) | WebSocket at `/ws` pushes full snapshot every 0.5s; client diffs `event_log` array to detect new entries |
| FEED-06 | Manual trigger keyboard shortcut fires a test entry event (for debugging) | Existing `POST /api/test-webhook` endpoint fires a test event; mapped to F4 via `event.code === "F4"` |
| KEYS-01 | Start/Stop system toggle (configurable key, default: F2) | `event.code === "F2"`; calls `POST /api/process/start` or `POST /api/process/stop` based on current `detector_running` state |
| KEYS-02 | Toggle detection overlay visibility (default: F3) | Same as FEED-02; `event.code === "F3"` toggles canvas opacity |
| KEYS-03 | Manual trigger test entry event (default: F4) | Same as FEED-06; `event.code === "F4"` calls `POST /api/test-webhook` |
| KEYS-04 | Emergency stop -- halt all processes immediately (default: Escape) | `event.code === "Escape"`; calls `POST /api/process/stop` then `POST /api/system/wake-lock/release` |
| KEYS-05 | All keyboard shortcuts use `keydown` with `event.code` (not deprecated `keypress`) | `document.addEventListener("keydown", handler)` with `event.code` not `event.key`; `event.preventDefault()` on F-keys to suppress browser defaults |
| KIOSK-02 | Web app runs in normal browser mode for development with DevTools access | Vite dev server on port 5173 with proxy to FastAPI 8080; no `--kiosk` flag in dev |
| KIOSK-03 | All UI text is in Romanian language (hardcoded, no i18n framework) | All strings in a single `ro.ts` constants file; DOM elements use these constants |
| KIOSK-04 | App works on Windows 11 Pro (production) and macOS (development) without code changes | No platform-specific code in frontend; all APIs are cross-browser; Node.js 25.6.1 available (exceeds Vite 7 minimum of 20.19+) |
| KIOSK-06 | Frontend is built with Vite and served by FastAPI StaticFiles in production | `vite build` outputs to `frontend_dist/`; FastAPI conditional StaticFiles mount already exists at `dashboard/web.py` line 326-328 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vite | 7.3.1 | Build tool and dev server | Current stable; `vanilla-ts` template is zero-framework; Rollup production build; native ESM with instant HMR |
| TypeScript | 5.x (bundled) | Type safety | Catches API shape mismatches at compile time; transpiled by esbuild (20-30x faster than tsc) |
| Vanilla TS | -- | No UI framework | Single-screen kiosk with ~5 DOM elements; React/Vue add 40-80KB runtime overhead for zero benefit |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None | -- | -- | All required APIs (WebSocket, fetch, Canvas 2D, KeyboardEvent) are browser-native |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla TS | React + Vite | 45KB runtime, JSX compilation, hook complexity -- overkill for a kiosk with no routing or component tree |
| Inline WebSocket reconnect | `reconnecting-websocket` npm | 5KB dependency for 30 lines of vanilla code; adds npm audit surface for a kiosk that should have zero transitive deps |
| Manual MJPEG parser | `@slamb/multipart-stream` npm | Library handles edge cases but adds a dependency; the MJPEG boundary is trivial (`--frame\r\n`) and frame detection via SOI marker (`0xFF 0xD8`) is reliable |

**Installation:**
```bash
# Scaffold (run once from project root)
npm create vite@latest frontend -- --template vanilla-ts
cd frontend && npm install
# No additional npm packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── index.html             # Single page entry point
├── package.json
├── tsconfig.json
├── vite.config.ts         # Proxy config for dev server
└── src/
    ├── main.ts            # Entry point -- wires all modules, starts MJPEG + WS
    ├── feed.ts            # MJPEG fetch-to-canvas renderer with boundary parser
    ├── ws.ts              # WebSocket client with exponential backoff reconnect
    ├── state.ts           # App state (single object, typed interface matching snapshot)
    ├── ui.ts              # DOM update functions (no logic, just rendering)
    ├── shortcuts.ts       # Keyboard shortcut bindings (keydown + event.code)
    ├── api.ts             # REST API call wrappers (start/stop/test-webhook)
    ├── ro.ts              # Romanian UI string constants
    └── style.css          # Fullscreen kiosk layout
```

### Pattern 1: MJPEG Fetch-to-Canvas with Object URL Revocation

**What:** Fetch the MJPEG multipart stream, parse boundaries, extract JPEG frames, draw to canvas, revoke object URLs immediately.

**When to use:** Always. This is the ONLY acceptable pattern for 24/7 MJPEG display. Never use `<img src="/video_feed">` -- it leaks memory.

**Backend boundary format** (from `dashboard/web.py` line 137, 180):
- Content-Type: `multipart/x-mixed-replace; boundary=frame`
- Boundary bytes: `--frame\r\n`
- Each part: `--frame\r\nContent-Type: image/jpeg\r\n\r\n<JPEG bytes>\r\n`

**Example:**
```typescript
// Source: PITFALLS.md Pitfall 1 + aruntj/mjpeg-readable-stream pattern
// Verified against dashboard/web.py _stream_generator boundary format

const SOI = 0xffd8; // JPEG Start of Image marker

export async function startMjpegCanvas(
  url: string,
  canvas: HTMLCanvasElement,
  signal?: AbortSignal
): Promise<void> {
  const ctx = canvas.getContext('2d')!;
  const response = await fetch(url, { signal });
  const reader = response.body!.getReader();

  let buffer = new Uint8Array(0);

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // Append chunk to buffer
    const newBuf = new Uint8Array(buffer.length + value.length);
    newBuf.set(buffer);
    newBuf.set(value, buffer.length);
    buffer = newBuf;

    // Find JPEG boundaries using SOI (0xFF 0xD8) and EOI (0xFF 0xD9)
    let startIdx = -1;
    for (let i = 0; i < buffer.length - 1; i++) {
      if (buffer[i] === 0xff && buffer[i + 1] === 0xd8) {
        startIdx = i;
        break;
      }
    }
    if (startIdx === -1) continue;

    let endIdx = -1;
    for (let i = startIdx + 2; i < buffer.length - 1; i++) {
      if (buffer[i] === 0xff && buffer[i + 1] === 0xd9) {
        endIdx = i + 2;
        break;
      }
    }
    if (endIdx === -1) continue;

    // Extract complete JPEG frame
    const jpegBytes = buffer.slice(startIdx, endIdx);
    buffer = buffer.slice(endIdx);

    // Render to canvas with explicit memory cleanup
    const blob = new Blob([jpegBytes], { type: 'image/jpeg' });
    const blobUrl = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(blobUrl); // CRITICAL: prevents memory leak
    };
    img.src = blobUrl;
  }
}
```

### Pattern 2: WebSocket with Exponential Backoff Reconnect

**What:** Connect to `/ws`, receive JSON snapshots every 0.5s, auto-reconnect with exponential backoff on disconnect.

**When to use:** Always. The kiosk must survive network hiccups, FastAPI restarts, and brief disconnections without operator intervention.

**Example:**
```typescript
// Source: dev.to WebSocket reconnection strategies + project PITFALLS.md Pitfall 9

export interface WsOptions {
  url: string;
  onMessage: (data: any) => void;
  onStatusChange?: (connected: boolean) => void;
  baseDelay?: number;    // default: 1000ms
  maxDelay?: number;     // default: 30000ms
  multiplier?: number;   // default: 2
}

export function createWsClient(opts: WsOptions): { close: () => void } {
  const { url, onMessage, onStatusChange } = opts;
  const baseDelay = opts.baseDelay ?? 1000;
  const maxDelay = opts.maxDelay ?? 30000;
  const multiplier = opts.multiplier ?? 2;

  let ws: WebSocket | null = null;
  let delay = baseDelay;
  let closed = false;
  let timer: number | null = null;

  function connect() {
    if (closed) return;
    ws = new WebSocket(url);

    ws.onopen = () => {
      delay = baseDelay; // Reset on successful connect
      onStatusChange?.(true);
    };

    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  function scheduleReconnect() {
    if (closed) return;
    const jitter = delay * 0.1 * Math.random();
    timer = window.setTimeout(connect, delay + jitter);
    delay = Math.min(delay * multiplier, maxDelay);
  }

  connect();

  return {
    close() {
      closed = true;
      if (timer !== null) clearTimeout(timer);
      ws?.close();
    },
  };
}
```

### Pattern 3: Keyboard Shortcuts with event.code

**What:** Listen for `keydown` events using `event.code` (physical key position) not `event.key` or deprecated `keypress`.

**When to use:** Always. `keypress` is deprecated and removed in Chrome 142+. `event.code` is layout-independent.

**Key code values** (from MDN Keyboard event code values):
- `"F2"` -- Start/Stop toggle (KEYS-01)
- `"F3"` -- Toggle overlay visibility (KEYS-02)
- `"F4"` -- Manual trigger test event (KEYS-03)
- `"Escape"` -- Emergency stop (KEYS-04)

**Example:**
```typescript
// Source: MDN KeyboardEvent.code + REQUIREMENTS.md KEYS-05

type ShortcutHandler = () => void | Promise<void>;

const shortcuts: Record<string, ShortcutHandler> = {};

export function registerShortcut(code: string, handler: ShortcutHandler): void {
  shortcuts[code] = handler;
}

export function initShortcuts(): void {
  document.addEventListener('keydown', (event: KeyboardEvent) => {
    const handler = shortcuts[event.code];
    if (handler) {
      event.preventDefault(); // Suppress browser default (e.g., F3 = Find)
      handler();
    }
  });
}
```

### Pattern 4: Vite Dev Proxy Configuration

**What:** Proxy `/api/*`, `/ws`, and `/video_feed` to FastAPI on port 8080 during development.

**When to use:** Always during development. In production, same-origin serving eliminates the need.

**Example:**
```typescript
// Source: Vite official docs (vite.dev/config/server-options)

import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,             // CRITICAL: without this, WebSocket upgrades fail silently
        changeOrigin: true,
      },
      '/video_feed': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../frontend_dist', // FastAPI serves from here via StaticFiles
  },
});
```

### Anti-Patterns to Avoid

- **`<img src="/video_feed">`:** Leaks memory at 15 FPS / 720p; browser tab crashes after 2-4 hours. Use fetch-to-canvas.
- **Setting `canvas.style.display = 'none'` to hide feed:** The fetch connection stays open but the canvas reference can be garbage collected. Use `canvas.style.opacity = '0'` instead.
- **Using `event.key` for shortcuts:** Layout-dependent; on a Romanian keyboard layout, keys may map differently. Use `event.code` which represents the physical key.
- **Using `keypress` event:** Deprecated and removed in Chrome 142+. Use `keydown`.
- **Reassigning `img.src = ''` to hide MJPEG:** Terminates the HTTP connection. Use CSS opacity.
- **No WebSocket reconnection logic:** Single WebSocket connection with no reconnect will show stale data after any network hiccup. Always implement backoff.
- **Hardcoded English strings in DOM:** All text must be Romanian from the start. Use a `ro.ts` constants file, not inline strings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MJPEG boundary parsing | Complex multipart HTTP parser | SOI/EOI JPEG marker detection | Backend boundary is fixed (`--frame`); detecting JPEG SOI (0xFF 0xD8) and EOI (0xFF 0xD9) markers in the byte stream is simpler and more reliable than parsing multipart headers |
| WebSocket reconnect | Full reconnecting-websocket library clone | 40-line exponential backoff wrapper | Pattern is well-known; 1s base, 30s cap, 2x multiplier, 10% jitter. No edge cases beyond what the code example covers |
| State management | Redux, MobX, or custom observable | Plain typed object + render function | 5 DOM elements, single source of truth -- a typed interface and a render function called on each WebSocket message is sufficient |
| i18n framework | i18next, FormatJS | `ro.ts` constants file | Romanian only, hardcoded; ~50 strings total; constants file is trivially maintainable |
| CSS framework | Tailwind, Bootstrap | Plain CSS in `style.css` | Kiosk layout is a fixed fullscreen grid with 5 elements; CSS framework adds build overhead for no benefit |

**Key insight:** This phase uses zero npm runtime dependencies. Every feature (MJPEG streaming, WebSocket, Canvas 2D, KeyboardEvent, DOM manipulation) is a browser-native API. The only tooling dependency is Vite itself for the build pipeline.

## Common Pitfalls

### Pitfall 1: MJPEG `<img>` Tag Memory Leak
**What goes wrong:** Using `<img src="/video_feed">` accumulates frames in browser memory. At 15 FPS / 720p, memory grows ~50MB/hour. After 2-4 hours, the tab OOMs.
**Why it happens:** Browser image decoder designed for static images buffers decoded MJPEG frames without releasing them.
**How to avoid:** Use fetch-to-canvas pattern with `URL.revokeObjectURL()` after each frame draw. See Pattern 1 above.
**Warning signs:** Chrome Task Manager shows tab memory growing monotonically; browser becomes sluggish after hours.

### Pitfall 2: Vite Proxy Silently Drops WebSocket Upgrades
**What goes wrong:** HTTP API calls work through Vite proxy, but WebSocket connections fail with "WebSocket connection failed" error.
**Why it happens:** Vite's proxy does not forward WebSocket upgrades by default. The `Connection: Upgrade` header is stripped.
**How to avoid:** Add `ws: true` to the `/ws` proxy entry in `vite.config.ts`. See Pattern 4 above.
**Warning signs:** HTTP endpoints work; WebSocket shows 400 or immediate close in browser Network tab; issue only in dev mode.

### Pitfall 3: F-Key Browser Defaults Override Shortcuts
**What goes wrong:** F3 opens browser Find dialog instead of toggling detection overlay. F2 may trigger browser rename in some contexts.
**Why it happens:** Function keys have default browser behaviors. Without `event.preventDefault()`, the browser handles them first.
**How to avoid:** Call `event.preventDefault()` in the keydown handler before executing the shortcut action.
**Warning signs:** Browser dialogs appearing when pressing F-keys; shortcut handler fires but UI is obscured by browser dialog.

### Pitfall 4: WebSocket State Goes Stale After Disconnect
**What goes wrong:** FPS counter freezes, entry events stop appearing, status panel shows stale data -- but the detector is still running.
**Why it happens:** WebSocket connection dropped (network hiccup, FastAPI restart, Chrome background throttling) with no reconnection logic.
**How to avoid:** Implement exponential backoff reconnect in the WebSocket client. See Pattern 2 above. Reset delay on successful connection.
**Warning signs:** FPS counter frozen; `WebSocket close code 1006` in console; stale data despite detector running.

### Pitfall 5: Snapshot Thumbnails Not Available in Event Log
**What goes wrong:** FEED-03 requires snapshot thumbnails in the entry log, but the current `push_event` call in `main.py` does NOT include the base64 snapshot in the event_log entry.
**Why it happens:** The snapshot is generated and added to the webhook payload (line 414-418 in `main.py`), but the `push_event` call (lines 429-437) only includes `event`, `timestamp`, `person_id`, `confidence`, and `queued`.
**How to avoid:** Modify `main.py` to include a truncated snapshot (or reference) in the event_log push_event for `person_entered` events. Alternatively, the frontend can display a placeholder and implement thumbnail loading in a later phase.
**Warning signs:** Entry log rows have no thumbnail column despite FEED-03 requiring it.

### Pitfall 6: Canvas Sizing Mismatch
**What goes wrong:** Canvas displays at wrong aspect ratio or appears blurry on high-DPI displays.
**Why it happens:** Canvas `width`/`height` attributes (resolution) differ from CSS width/height (display size). On Retina displays, 1 CSS pixel = 2+ device pixels.
**How to avoid:** Set canvas width/height to match the JPEG frame's natural dimensions on first load. For display sizing, use CSS `width: 100%; height: auto; object-fit: contain` on the canvas container. For this kiosk (non-Retina production target), pixel ratio scaling is not needed.
**Warning signs:** Feed appears stretched, squished, or blurry.

## Code Examples

### WebSocket Snapshot Payload Structure
```typescript
// Source: dashboard/web.py DashboardState.snapshot() lines 81-97
// This is the exact JSON the WebSocket sends every 0.5s

interface DashboardSnapshot {
  frame_number: number;
  fps: number;
  current_people: number;
  entries_today: number;
  last_entry_time: string | null;
  uptime_seconds: number;
  event_log: EventLogEntry[];
  tracked_people: TrackedPerson[];
  camera_connected: boolean;
  webhook_status: Record<string, any>;
  calibration: Record<string, any>;
  detector_running: boolean;
  wake_lock_active: boolean;
}

interface EventLogEntry {
  event: string;           // "person_entered" | "person_exited" | "test_webhook"
  timestamp: string;       // ISO 8601
  person_id: number;
  confidence: number;
  queued?: boolean;        // only on person_entered events
  // NOTE: snapshot thumbnail NOT currently included -- see Pitfall 5
}

interface TrackedPerson {
  person_id: number;
  direction: string;
  score: number;
  confidence: number;
}
```

### Romanian UI String Constants
```typescript
// Source: REQUIREMENTS.md KIOSK-03 -- all UI text in Romanian, hardcoded

export const RO = {
  // Header
  APP_TITLE: 'Detector Intrare Clinica',

  // Status panel labels
  FPS: 'FPS',
  ACTIVE_TRACKS: 'Persoane active',
  ENTRIES_TODAY: 'Intrari astazi',
  UPTIME: 'Timp functionare',
  WEBHOOK_STATUS: 'Webhook',
  DETECTOR_STATUS: 'Detector',
  WAKE_LOCK: 'Blocare ecran',

  // Status values
  RUNNING: 'Activ',
  STOPPED: 'Oprit',
  CONNECTED: 'Conectat',
  DISCONNECTED: 'Deconectat',
  HEALTHY: 'Functional',
  ERROR: 'Eroare',

  // Entry log
  ENTRY_LOG_TITLE: 'Jurnal intrari',
  TIMESTAMP: 'Ora',
  PERSON_ID: 'ID Persoana',
  CONFIDENCE: 'Incredere',
  SNAPSHOT: 'Captura',

  // Keyboard shortcuts
  SHORTCUTS_HINT: 'F2: Start/Stop | F3: Overlay | F4: Test | Esc: Oprire urgenta',

  // Connection status
  WS_CONNECTING: 'Se conecteaza...',
  WS_CONNECTED: 'Conectat la server',
  WS_DISCONNECTED: 'Deconectat -- se reincearca...',

  // Feed
  FEED_LOADING: 'Se incarca feed-ul video...',
  FEED_ERROR: 'Eroare la incarcarea feed-ului',
  NO_FEED: 'Feed indisponibil',
} as const;
```

### Status Panel DOM Update
```typescript
// Source: dashboard/templates/index.html existing render() pattern, adapted to TypeScript

export function updateStatusPanel(data: DashboardSnapshot): void {
  setText('fps-value', data.fps.toFixed(1));
  setText('people-value', String(data.current_people));
  setText('entries-value', String(data.entries_today));
  setText('uptime-value', formatUptime(data.uptime_seconds));

  setBadge('detector-badge', data.detector_running ? RO.RUNNING : RO.STOPPED,
    data.detector_running ? 'ok' : 'err');
  setBadge('webhook-badge',
    data.webhook_status?.last_error ? RO.ERROR : RO.HEALTHY,
    data.webhook_status?.last_error ? 'warn' : 'ok');
  setBadge('ws-badge', RO.CONNECTED, 'ok');
}

function setText(id: string, text: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
}
```

### Entry Log with New Event Detection
```typescript
// Source: dashboard/web.py event_log is a deque(maxlen=100), newest first

let lastEventCount = 0;

export function updateEntryLog(
  eventLog: EventLogEntry[],
  container: HTMLElement
): void {
  // Detect new entries (event_log is newest-first, max 100)
  const newCount = eventLog.length;
  if (newCount > lastEventCount) {
    // New entries added at the front
    const newEntries = eventLog.slice(0, newCount - lastEventCount);
    for (const entry of newEntries) {
      const row = createEntryRow(entry);
      container.prepend(row);
    }
    // Cap displayed rows at 100
    while (container.children.length > 100) {
      container.lastElementChild?.remove();
    }
  }
  lastEventCount = newCount;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `<img src="/video_feed">` MJPEG | fetch-to-canvas with `URL.revokeObjectURL()` | Always for 24/7 kiosk | Prevents memory leak; mandatory for kiosk |
| `keypress` event | `keydown` with `event.code` | Chrome 142+ (2025) | `keypress` removed from Chrome; code is layout-independent |
| Socket.IO / reconnecting-websocket | Vanilla WebSocket + backoff | Current best practice | Zero dependencies; 30-40 lines; sufficient for single-connection kiosk |
| `event.keyCode` | `event.code` | Deprecated since 2017 | keyCode is layout-dependent and marked as deprecated |

**Deprecated/outdated:**
- `keypress` event: Removed in Chrome 142+. Use `keydown` with `event.code`.
- `event.keyCode`: Deprecated. Use `event.code` (physical key) or `event.key` (logical key).
- `<img>` for MJPEG in long-running apps: Memory leak risk. Use fetch-to-canvas.

## Open Questions

1. **Snapshot thumbnails in event_log (FEED-03)**
   - What we know: `main.py` generates base64 JPEG snapshots for `person_entered` events but only includes them in the webhook payload, not in the `push_event` call to `DashboardState`.
   - What's unclear: Whether to modify `main.py` to include a truncated snapshot in the event_log or defer thumbnail display to a later approach.
   - Recommendation: Add a `snapshot` field (truncated to 320px wide, ~5-10KB base64) to the `push_event` call for `person_entered` events in `main.py`. This is a ~3 line change. The frontend then displays it as an `<img src="data:image/jpeg;base64,...">` in each entry row. This keeps the WebSocket payload reasonable (~10KB per event, max 100 events = ~1MB total in snapshot).

2. **MJPEG fetch-to-canvas performance at 15 FPS**
   - What we know: The pattern is well-documented and used in production MJPEG viewers. Object URL creation/revocation per frame is the standard approach.
   - What's unclear: Whether `requestAnimationFrame` throttling is needed to avoid drawing faster than the display refresh rate.
   - Recommendation: Draw on `img.onload` (which naturally throttles to frame arrival rate of ~15 FPS). If CPU usage is high, add `requestAnimationFrame` gating. Monitor via Chrome Task Manager during 30-minute test.

3. **Entry log event diffing strategy**
   - What we know: WebSocket sends the full `event_log` array (up to 100 entries) every 0.5s. Naively replacing all DOM rows every 500ms is wasteful.
   - What's unclear: Whether to diff by array length, by last-seen event timestamp, or by a sequence counter.
   - Recommendation: Track `event_log.length` and prepend only the delta entries. The event_log is a deque with newest-first ordering and maxlen=100, so length comparison is sufficient to detect new entries. A full DOM rebuild is acceptable as a fallback after WebSocket reconnect.

## Sources

### Primary (HIGH confidence)
- Vite official docs -- https://vite.dev/guide/ -- version 7.3.1 confirmed, Node.js 20.19+ requirement
- Vite server proxy options -- https://vite.dev/config/server-options -- `ws: true` syntax confirmed
- MDN KeyboardEvent.code -- https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code -- physical key code values
- MDN Keyboard event code values -- https://developer.mozilla.org/en-US/docs/Web/API/UI_Events/Keyboard_event_code_values -- F2, F3, F4, Escape values
- Existing codebase: `dashboard/web.py` -- MJPEG boundary format (`--frame\r\n`), WebSocket `/ws` endpoint, `DashboardState.snapshot()` payload structure
- Existing codebase: `main.py` lines 395-437 -- event_log push_event format, snapshot generation
- Existing codebase: `dashboard/templates/index.html` -- existing dashboard UI rendering pattern

### Secondary (MEDIUM confidence)
- aruntj/mjpeg-readable-stream -- https://github.com/aruntj/mjpeg-readable-stream -- fetch ReadableStream MJPEG pattern, SOI/EOI marker detection approach
- WebSocket reconnection strategies -- https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1 -- exponential backoff pattern
- Resilient WebSocket in TypeScript -- https://peerdh.com/blogs/programming-insights/building-resilient-websocket-connections-in-typescript-applications -- TypeScript reconnect patterns
- WHATWG Fetch multipart discussion -- https://github.com/whatwg/fetch/issues/1021 -- ReadableStream multipart handling

### Tertiary (LOW confidence)
- @slamb/multipart-stream npm -- https://www.npmjs.com/package/@slamb/multipart-stream -- alternative multipart parser (not recommended for use, but validates the pattern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Vite 7.3.1 confirmed on npm; vanilla-ts template well-documented; Node.js 25.6.1 available locally
- Architecture: HIGH -- patterns verified against existing codebase (`dashboard/web.py`), MDN docs, and project research (ARCHITECTURE.md, PITFALLS.md)
- Pitfalls: HIGH -- all pitfalls traced to existing codebase analysis (snapshot gap), official browser docs (keypress deprecation), and verified project research
- MJPEG fetch-to-canvas: MEDIUM -- pattern is well-documented but the exact SOI/EOI parsing implementation should be validated with a 30-minute memory stability test

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain -- Vite versioning and browser APIs are mature)
