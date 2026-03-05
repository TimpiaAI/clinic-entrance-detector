/**
 * App state matching DashboardSnapshot interface.
 *
 * Single mutable state object updated on each WebSocket message.
 * The onStateUpdate callback is invoked after each update for
 * downstream consumers (UI rendering, logging, etc.).
 */

import type { DashboardSnapshot } from './types.ts';

export const appState: DashboardSnapshot = {
  frame_number: 0,
  fps: 0,
  current_people: 0,
  entries_today: 0,
  last_entry_time: null,
  uptime_seconds: 0,
  event_log: [],
  tracked_people: [],
  camera_connected: false,
  webhook_status: {},
  calibration: {},
  detector_running: false,
  wake_lock_active: false,
};

export let onStateUpdate: ((state: DashboardSnapshot) => void) | null = null;

export function setOnStateUpdate(
  callback: ((state: DashboardSnapshot) => void) | null,
): void {
  onStateUpdate = callback;
}

export function updateState(snapshot: DashboardSnapshot): void {
  appState.frame_number = snapshot.frame_number;
  appState.fps = snapshot.fps;
  appState.current_people = snapshot.current_people;
  appState.entries_today = snapshot.entries_today;
  appState.last_entry_time = snapshot.last_entry_time;
  appState.uptime_seconds = snapshot.uptime_seconds;
  appState.event_log = snapshot.event_log;
  appState.tracked_people = snapshot.tracked_people;
  appState.camera_connected = snapshot.camera_connected;
  appState.webhook_status = snapshot.webhook_status;
  appState.calibration = snapshot.calibration;
  appState.detector_running = snapshot.detector_running;
  appState.wake_lock_active = snapshot.wake_lock_active;

  if (onStateUpdate) {
    onStateUpdate(appState);
  }
}
