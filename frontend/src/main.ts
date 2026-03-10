/**
 * Entry point -- wires MJPEG feed, WebSocket state, workflow,
 * system control, and keyboard shortcuts together.
 */

import { apiTestWebhook, apiSimulateEntry } from './api.ts';
import { startMjpegCanvas } from './feed.ts';
import { registerShortcut, initShortcuts } from './shortcuts.ts';
import { updateState, setOnStateUpdate } from './state.ts';
import './style.css';
import type { DashboardSnapshot } from './types.ts';
import { updateStatusPanel, updateEntryLog, updateWsBadge, resetEntryLog } from './ui.ts';
import { initVideo, onUserGesture, checkForPersonEntered } from './video.ts';
import { createWsClient } from './ws.ts';
import { initWorkflow, checkForPersonEnteredWorkflow, getWorkflowState } from './workflow.ts';
import {
  initSystemControl,
  toggleSystem,
  emergencyStop,
  onStateUpdateForCrashDetection,
  autoStart,
} from './system-control.ts';

document.addEventListener('DOMContentLoaded', () => {
  // --- MJPEG feed ---
  const canvas = document.getElementById('feed-canvas') as HTMLCanvasElement | null;
  if (canvas) {
    startMjpegCanvas('/video_feed', canvas);
  } else {
    console.error('main: #feed-canvas not found');
  }

  // --- Initialize modules ---
  initVideo();
  initWorkflow();
  initSystemControl();

  // --- Unmute video on first user interaction (click or keypress) ---
  const unmuteOnce = () => {
    onUserGesture();
    document.removeEventListener('click', unmuteOnce);
    document.removeEventListener('keydown', unmuteOnce);
  };
  document.addEventListener('click', unmuteOnce);
  document.addEventListener('keydown', unmuteOnce);

  // --- Entry log container ---
  const logBody = document.getElementById('log-body') as HTMLTableSectionElement | null;

  // --- WebSocket state updates ---
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

  createWsClient({
    url: wsUrl,
    onMessage: updateState,
    onStatusChange: (connected: boolean) => {
      updateWsBadge(connected);
      if (connected) {
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
    onStateUpdateForCrashDetection(state);

    // Route person_entered events based on workflow state
    if (getWorkflowState() === 'stopped') {
      // Phase 3 behavior: linear instruction sequence for F4 testing
      checkForPersonEntered(state.event_log);
    }
    // Workflow handles person_entered via its own event log diffing
    checkForPersonEnteredWorkflow(state.event_log);
  });

  // --- Keyboard shortcuts ---
  // F2: Start/Stop system toggle (CTRL-01)
  registerShortcut('F2', async () => {
    onUserGesture(); // Capture first keypress to unmute video
    await toggleSystem();
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

  // Escape: Emergency stop -- immediately stops everything (CTRL-02)
  registerShortcut('Escape', () => {
    emergencyStop();
  });

  initShortcuts();

  // --- Trigger entry button ---
  const triggerBtn = document.getElementById('trigger-entry-btn') as HTMLButtonElement | null;
  if (triggerBtn) {
    triggerBtn.addEventListener('click', async () => {
      await apiSimulateEntry();
    });
  }

  // --- Auto-start detection pipeline on page load (CTRL-03) ---
  autoStart();
});
