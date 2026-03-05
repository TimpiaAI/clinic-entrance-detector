/**
 * System lifecycle orchestration.
 *
 * Coordinates start/stop of the detector subprocess, wake-lock,
 * audio initialization, workflow state machine, and health monitoring.
 *
 * Provides:
 * - startSystem() / stopSystem() for F2 toggle
 * - emergencyStop() for Escape key
 * - autoStart() for page-load detector + wake-lock activation
 * - Health monitoring via 5s polling + WebSocket state diffing
 * - Crash detection with Romanian alert and restart button
 */

import {
  apiStartDetector,
  apiStopDetector,
  apiDetectorStatus,
  apiWakeLockActivate,
  apiWakeLockRelease,
} from './api.ts';
import { initAudio, isMicReady } from './audio.ts';
import type { DashboardSnapshot } from './types.ts';
import {
  hideCrashAlert,
  hideTranscriptionPanel,
  showCrashAlert,
  updateSystemButton,
} from './ui.ts';
import { startWorkflow, stopWorkflow } from './workflow.ts';

// ---------------------------------------------------------------------------
//  Module-level state
// ---------------------------------------------------------------------------

let systemRunning = false;
let healthInterval: ReturnType<typeof setInterval> | null = null;
let wasDetectorRunning = false;

// ---------------------------------------------------------------------------
//  Health monitoring (CTRL-04)
// ---------------------------------------------------------------------------

/**
 * Start 5-second polling of /api/process/status for health monitoring.
 */
function startHealthMonitor(): void {
  stopHealthMonitor();
  healthInterval = setInterval(async () => {
    try {
      const status = await apiDetectorStatus();
      if (systemRunning && !status.running) {
        // Detector stopped unexpectedly (crash or external kill)
        handleCrashDetected();
      }
    } catch {
      // Network error -- ignore, WebSocket will catch it
    }
  }, 5_000);
}

/**
 * Stop the health monitoring interval.
 */
function stopHealthMonitor(): void {
  if (healthInterval !== null) {
    clearInterval(healthInterval);
    healthInterval = null;
  }
}

/**
 * Handle a detected crash: stop workflow, show alert, reset state.
 */
function handleCrashDetected(): void {
  stopHealthMonitor();
  stopWorkflow();
  systemRunning = false;
  updateSystemButton(false);
  showCrashAlert(handleRestart);
}

/**
 * Restart the system after a crash alert.
 */
async function handleRestart(): Promise<void> {
  hideCrashAlert();
  await startSystem();
}

// ---------------------------------------------------------------------------
//  WebSocket-based crash detection (CTRL-05)
// ---------------------------------------------------------------------------

/**
 * Check WebSocket state updates for unexpected detector_running transitions.
 * Called from main.ts setOnStateUpdate callback on every snapshot.
 *
 * Detects: systemRunning && wasDetectorRunning && !state.detector_running
 * This is faster than polling -- WebSocket pushes at ~2 Hz.
 */
export function onStateUpdateForCrashDetection(state: DashboardSnapshot): void {
  if (systemRunning && wasDetectorRunning && !state.detector_running) {
    // Unexpected crash detected via WebSocket
    handleCrashDetected();
  }
  wasDetectorRunning = state.detector_running;
}

// ---------------------------------------------------------------------------
//  Start / Stop / Emergency Stop
// ---------------------------------------------------------------------------

/**
 * Start the full system: detector + wake-lock + audio + workflow + health monitor.
 * Called by F2 toggle and crash restart.
 */
export async function startSystem(): Promise<void> {
  updateSystemButton(false, true); // Show "Se porneste..."
  try {
    await apiStartDetector();
    await apiWakeLockActivate();

    // Initialize audio if not already ready (user gesture required)
    if (!isMicReady()) {
      await initAudio(); // May fail silently -- that's OK
    }

    startWorkflow(); // Transitions workflow to idle, starts idle video loop
    startHealthMonitor();
    systemRunning = true;
    wasDetectorRunning = true;
    updateSystemButton(true); // Show "Stop"
  } catch (err) {
    console.error('system-control: startSystem failed', err);
    systemRunning = false;
    updateSystemButton(false);
  }
}

/**
 * Stop the full system gracefully: workflow + health + detector + wake-lock.
 * Called by F2 toggle and stop button.
 */
export async function stopSystem(): Promise<void> {
  updateSystemButton(true, true); // Show "Se opreste..."
  try {
    stopWorkflow(); // Abort workflow, hide video, clear data
    stopHealthMonitor();
    await apiStopDetector();
    await apiWakeLockRelease();
    hideCrashAlert();
    systemRunning = false;
    wasDetectorRunning = false;
    updateSystemButton(false); // Show "Start"
  } catch (err) {
    console.error('system-control: stopSystem failed', err);
    systemRunning = false;
    updateSystemButton(false);
  }
}

/**
 * Emergency stop -- immediate, no transitioning UI.
 * Called by Escape key. Aborts active recordings first.
 */
export function emergencyStop(): void {
  stopWorkflow(); // Aborts recording via cancellation flag
  stopHealthMonitor();
  hideTranscriptionPanel();
  hideCrashAlert();
  systemRunning = false;
  wasDetectorRunning = false;
  updateSystemButton(false);

  // Fire-and-forget API calls (emergency -- don't await)
  apiStopDetector().catch(() => {});
  apiWakeLockRelease().catch(() => {});
}

/**
 * Toggle system on/off. Wired to F2 and the system toggle button.
 */
export async function toggleSystem(): Promise<void> {
  if (systemRunning) {
    await stopSystem();
  } else {
    await startSystem();
  }
}

// ---------------------------------------------------------------------------
//  Auto-start (CTRL-03)
// ---------------------------------------------------------------------------

/**
 * Auto-start the detection pipeline on page load.
 * Starts detector + wake-lock + health monitor but NOT the workflow.
 * Workflow requires F2 press to activate (deliberate: detection != interaction).
 *
 * Skip with ?no-autostart query param for development.
 */
export async function autoStart(): Promise<void> {
  if (new URLSearchParams(window.location.search).has('no-autostart')) return;
  try {
    await apiStartDetector();
    await apiWakeLockActivate();
    startHealthMonitor();
    systemRunning = true;
    wasDetectorRunning = true;
    updateSystemButton(true);
  } catch (err) {
    console.warn('system-control: auto-start failed', err);
  }
}

// ---------------------------------------------------------------------------
//  Initialization
// ---------------------------------------------------------------------------

/**
 * Initialize system control: wire the toggle button click handler.
 */
export function initSystemControl(): void {
  const btn = document.getElementById('system-toggle-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      toggleSystem();
    });
  }
}

/**
 * Returns whether the system is currently running.
 */
export function isSystemRunning(): boolean {
  return systemRunning;
}
