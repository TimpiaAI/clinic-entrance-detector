/**
 * Entry point -- wires MJPEG feed, WebSocket state, and app state together.
 */

import { apiStartDetector, apiStopDetector, apiTestWebhook, apiWakeLockRelease } from './api.ts';
import { startMjpegCanvas } from './feed.ts';
import { registerShortcut, initShortcuts } from './shortcuts.ts';
import { appState, updateState, setOnStateUpdate } from './state.ts';
import './style.css';
import type { DashboardSnapshot } from './types.ts';
import { createWsClient } from './ws.ts';

document.addEventListener('DOMContentLoaded', () => {
  // --- MJPEG feed ---
  const canvas = document.getElementById('feed-canvas') as HTMLCanvasElement | null;
  if (canvas) {
    startMjpegCanvas('/video_feed', canvas);
  } else {
    console.error('main: #feed-canvas not found');
  }

  // --- WebSocket state updates ---
  // Construct ws:// or wss:// URL matching current page protocol
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

  createWsClient({
    url: wsUrl,
    onMessage: updateState,
    onStatusChange: (connected: boolean) => {
      console.log(`ws: ${connected ? 'connected' : 'disconnected'}`);
    },
  });

  // --- State update callback ---
  setOnStateUpdate((state: DashboardSnapshot) => {
    // Temporary: log FPS until UI rendering is added in Plan 02-02
    console.log(`fps: ${state.fps.toFixed(1)} | people: ${state.current_people} | entries: ${state.entries_today}`);
  });

  // --- Keyboard shortcuts ---
  // F2: Start/Stop detector toggle (KEYS-01)
  registerShortcut('F2', async () => {
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
