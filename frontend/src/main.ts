/**
 * Entry point -- wires MJPEG feed, WebSocket state, and app state together.
 */

import { startMjpegCanvas } from './feed.ts';
import { updateState, setOnStateUpdate } from './state.ts';
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
});
