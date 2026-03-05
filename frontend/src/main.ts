/**
 * Entry point -- wires MJPEG feed, WebSocket state, and UI together.
 */

import { apiStartDetector, apiStopDetector, apiTestWebhook, apiWakeLockRelease } from './api.ts';
import { initAudio, isMicReady } from './audio.ts';
import { startMjpegCanvas } from './feed.ts';
import { registerShortcut, initShortcuts } from './shortcuts.ts';
import { appState, updateState, setOnStateUpdate } from './state.ts';
import './style.css';
import type { DashboardSnapshot } from './types.ts';
import { updateStatusPanel, updateEntryLog, updateWsBadge, resetEntryLog } from './ui.ts';
import { initVideo, startIdleLoop, onUserGesture, checkForPersonEntered } from './video.ts';
import { createWsClient } from './ws.ts';

document.addEventListener('DOMContentLoaded', () => {
  // --- MJPEG feed ---
  const canvas = document.getElementById('feed-canvas') as HTMLCanvasElement | null;
  if (canvas) {
    startMjpegCanvas('/video_feed', canvas);
  } else {
    console.error('main: #feed-canvas not found');
  }

  // --- Video overlay ---
  initVideo();
  startIdleLoop();

  // --- Entry log container ---
  const logBody = document.getElementById('log-body') as HTMLTableSectionElement | null;

  // --- WebSocket state updates ---
  // Construct ws:// or wss:// URL matching current page protocol
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

  createWsClient({
    url: wsUrl,
    onMessage: updateState,
    onStatusChange: (connected: boolean) => {
      updateWsBadge(connected);
      if (connected) {
        // Reset entry log counter on reconnect so next snapshot rebuilds fully
        resetEntryLog();
        if (logBody) logBody.innerHTML = '';
      }
    },
  });

  // --- State update callback ---
  setOnStateUpdate((state: DashboardSnapshot) => {
    updateStatusPanel(state);
    if (logBody) {
      updateEntryLog(state.event_log, logBody);
    }
    checkForPersonEntered(state.event_log);
  });

  // --- Keyboard shortcuts ---
  // F2: Start/Stop detector toggle (KEYS-01)
  registerShortcut('F2', async () => {
    onUserGesture(); // Capture first keypress to unmute video

    // Initialize audio on first Start press (user gesture required for mic + AudioContext)
    if (!isMicReady()) {
      const granted = await initAudio();
      if (!granted) {
        console.warn('main: mic permission denied on F2');
        // Continue anyway -- detector can still start, audio will fail gracefully later
      }
    }

    if (appState.detector_running) {
      await apiStopDetector();
    } else {
      await apiStartDetector();
    }
  });

  // F3: Toggle overlay visibility without breaking MJPEG connection (KEYS-02, FEED-02)
  registerShortcut('F3', () => {
    const feedCanvas = document.getElementById('feed-canvas') as HTMLCanvasElement;
    feedCanvas.style.opacity = feedCanvas.style.opacity === '0' ? '1' : '0';
  });

  // F4: Fire test entry event (KEYS-03, FEED-06)
  registerShortcut('F4', async () => {
    await apiTestWebhook();
  });

  // Escape: Emergency stop -- stops detector and releases wake lock (KEYS-04)
  registerShortcut('Escape', async () => {
    await apiStopDetector();
    await apiWakeLockRelease();
  });

  initShortcuts();
});
