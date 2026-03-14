/**
 * DOM update functions for status panel and entry log table.
 *
 * Updates are driven by the onStateUpdate callback in main.ts,
 * called on every WebSocket message (~2 Hz). Functions use
 * direct DOM manipulation for minimal overhead in a 24/7 kiosk.
 *
 * Romanian labels are inline constants (will be centralized in
 * Plan 03's ro.ts).
 */

import type { DashboardSnapshot, EventLogEntry, PatientData, TranscribeResult } from './types.ts';
import { RO } from './ro.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Set textContent of an element by ID. No-op if element not found. */
function setText(id: string, text: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/** Set badge text and status class (ok | warn | err). */
function setBadge(id: string, text: string, status: 'ok' | 'warn' | 'err'): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = `badge badge-${status}`;
}

/** Format seconds into `Xh Ym Zs`. */
export function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
}

/** Parse ISO 8601 timestamp and return `HH:MM:SS` in local time. */
export function formatTime(isoString: string): string {
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '--:--:--';
  return d.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ---------------------------------------------------------------------------
// Status Panel
// ---------------------------------------------------------------------------

/**
 * Update all status panel DOM elements with live metrics.
 * Called on every WebSocket message.
 */
export function updateStatusPanel(data: DashboardSnapshot): void {
  setText('fps-value', data.fps.toFixed(1));
  setText('people-value', String(data.current_people));
  setText('entries-value', String(data.entries_today));
  setText('uptime-value', formatUptime(data.uptime_seconds));

  // Detector status
  setBadge(
    'detector-badge',
    data.detector_running ? 'Activ' : 'Oprit',
    data.detector_running ? 'ok' : 'err',
  );

  // Webhook status
  const webhookError = data.webhook_status?.last_error;
  setBadge(
    'webhook-badge',
    webhookError ? 'Eroare' : 'Functional',
    webhookError ? 'err' : 'ok',
  );

  // Wake lock status
  setBadge(
    'wakelock-badge',
    data.wake_lock_active ? 'Activ' : 'Oprit',
    data.wake_lock_active ? 'ok' : 'warn',
  );
}

/**
 * Update WebSocket connection badge independently (called from onStatusChange).
 */
export function updateWsBadge(connected: boolean): void {
  setBadge(
    'ws-badge',
    connected ? 'Conectat' : 'Deconectat',
    connected ? 'ok' : 'err',
  );
}

// ---------------------------------------------------------------------------
// Entry Log
// ---------------------------------------------------------------------------

/** Track how many events we have already rendered. */
let lastEventCount = 0;

/**
 * Update the entry log table with new detection events.
 *
 * Compares eventLog.length to lastEventCount to detect new entries.
 * New rows are prepended (newest first). DOM is capped at 100 rows.
 */
export function updateEntryLog(eventLog: EventLogEntry[], container: HTMLElement): void {
  const newCount = eventLog.length;

  if (newCount <= lastEventCount) {
    // No new events (or log was trimmed server-side)
    if (newCount < lastEventCount) {
      // Server reset or trimmed -- full rebuild
      container.innerHTML = '';
      lastEventCount = 0;
    } else {
      return;
    }
  }

  // New entries are at the front of the array (index 0 = newest).
  // We need to render entries from index 0 to (newCount - lastEventCount - 1).
  const entriesToAdd = newCount - lastEventCount;

  // Build rows for new entries (iterate in reverse so oldest of the new batch
  // is prepended first, then newer ones push it down -- resulting in newest at top).
  for (let i = entriesToAdd - 1; i >= 0; i--) {
    const entry = eventLog[i];
    if (!entry) continue;

    const row = document.createElement('tr');

    // Timestamp cell
    const tdTime = document.createElement('td');
    tdTime.textContent = formatTime(entry.timestamp);
    row.appendChild(tdTime);

    // Person ID cell
    const tdId = document.createElement('td');
    tdId.textContent = String(entry.person_id);
    row.appendChild(tdId);

    // Confidence cell
    const tdConf = document.createElement('td');
    tdConf.textContent = `${(entry.confidence * 100).toFixed(0)}%`;
    row.appendChild(tdConf);

    // Snapshot cell
    const tdSnap = document.createElement('td');
    if (entry.snapshot) {
      const img = document.createElement('img');
      img.src = `data:image/jpeg;base64,${entry.snapshot}`;
      img.width = 64;
      img.height = 48;
      img.alt = `Persoana ${entry.person_id}`;
      img.className = 'snapshot-thumb';
      tdSnap.appendChild(img);
    } else {
      tdSnap.textContent = '\u2014'; // em-dash
    }
    row.appendChild(tdSnap);

    // Prepend row (newest at top)
    container.insertBefore(row, container.firstChild);
  }

  lastEventCount = newCount;

  // Cap displayed rows at 100 to prevent DOM performance degradation
  const maxRows = 100;
  while (container.children.length > maxRows) {
    container.removeChild(container.lastChild as Node);
  }
}

/**
 * Reset lastEventCount (call on WebSocket reconnect for full rebuild).
 */
export function resetEntryLog(): void {
  lastEventCount = 0;
}

// ---------------------------------------------------------------------------
// Transcription Panel
// ---------------------------------------------------------------------------

/**
 * Show recording state -- pulsing red indicator + "Inregistrare..." text.
 * Called by workflow when MediaRecorder starts.
 */
export function showRecordingState(): void {
  const panel = document.getElementById('transcription-panel');
  const indicator = document.getElementById('recording-indicator');
  const statusText = document.getElementById('status-text');
  const result = document.getElementById('transcription-result');
  const actions = document.getElementById('transcription-actions');

  if (panel) panel.classList.add('visible');
  if (indicator) indicator.classList.add('active');
  if (statusText) statusText.textContent = RO.RECORDING;
  if (result) result.classList.remove('visible');
  if (actions) actions.classList.remove('visible');
}

/**
 * Update the recording status text with live interim transcription.
 */
export function updateRecordingInterim(text: string): void {
  const statusText = document.getElementById('status-text');
  if (statusText) statusText.textContent = text || RO.RECORDING;
}

/**
 * Show editable input field for CNP or email during recording.
 * The field updates live from voice and can be edited by keyboard.
 */
export function showEditableField(label: string, value?: string): void {
  const container = document.getElementById('editable-field-container');
  const labelEl = document.getElementById('editable-field-label');
  const input = document.getElementById('editable-field-input') as HTMLInputElement | null;
  const statusBar = document.getElementById('transcription-status');

  // Hide the "Inregistrare..." bar for editable fields
  if (statusBar) statusBar.style.display = 'none';

  if (container) container.classList.add('visible');
  if (labelEl) labelEl.textContent = label;
  if (input) {
    input.value = value || '';
    input.classList.add('recording');
    input.focus();
  }
}

/**
 * Update the editable field value (from live transcription).
 * Only updates if the user hasn't manually edited (field still has recording class).
 */
export function updateEditableField(value: string): void {
  const input = document.getElementById('editable-field-input') as HTMLInputElement | null;
  if (input && input.classList.contains('recording')) {
    input.value = value;
  }
}

/**
 * Get the current editable field value (may have been manually edited).
 */
export function getEditableFieldValue(): string {
  const input = document.getElementById('editable-field-input') as HTMLInputElement | null;
  return input?.value || '';
}

/**
 * Hide the editable field and remove recording state.
 */
export function hideEditableField(): void {
  const container = document.getElementById('editable-field-container');
  const input = document.getElementById('editable-field-input') as HTMLInputElement | null;
  const statusBar = document.getElementById('transcription-status');

  if (container) container.classList.remove('visible');
  if (input) {
    input.classList.remove('recording');
    input.value = '';
  }
  // Restore the status bar
  if (statusBar) statusBar.style.display = '';
}

/**
 * Show processing state -- hide recording indicator, show "Procesare..." text.
 * Called when recording stops and audio is being sent to backend.
 */
export function showProcessingState(): void {
  const indicator = document.getElementById('recording-indicator');
  const statusText = document.getElementById('status-text');

  if (indicator) indicator.classList.remove('active');
  if (statusText) statusText.textContent = RO.PROCESSING;
}

/**
 * Show transcription result with text, CNP, email and Confirma/Repeta buttons.
 * The onConfirm and onRetry callbacks are provided by the workflow state machine.
 */
export function showTranscriptionResult(
  data: TranscribeResult,
  onConfirm: () => void,
  onRetry: () => void,
): void {
  const statusText = document.getElementById('status-text');
  const result = document.getElementById('transcription-result');
  const actions = document.getElementById('transcription-actions');
  const resultText = document.getElementById('result-text');
  const resultCnp = document.getElementById('result-cnp');
  const resultEmail = document.getElementById('result-email');

  // Update status line
  if (statusText) statusText.textContent = RO.CONFIRM_PROMPT;

  // Show result fields
  if (resultText) resultText.textContent = data.text || RO.TRANSCRIPTION_EMPTY;
  if (resultCnp) {
    resultCnp.textContent = data.cnp ? `${RO.CNP_LABEL}: ${data.cnp}` : '';
    resultCnp.style.display = data.cnp ? 'block' : 'none';
  }
  if (resultEmail) {
    resultEmail.textContent = data.email ? `${RO.EMAIL_LABEL}: ${data.email}` : '';
    resultEmail.style.display = data.email ? 'block' : 'none';
  }
  if (result) result.classList.add('visible');

  // Build action buttons
  if (actions) {
    actions.innerHTML = '';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn-confirm';
    confirmBtn.textContent = RO.CONFIRM_ACCEPT;
    confirmBtn.addEventListener('click', onConfirm, { once: true });

    const retryBtn = document.createElement('button');
    retryBtn.className = 'btn-retry';
    retryBtn.textContent = RO.CONFIRM_RETRY;
    retryBtn.addEventListener('click', onRetry, { once: true });

    actions.appendChild(confirmBtn);
    actions.appendChild(retryBtn);
    actions.classList.add('visible');
  }
}

/**
 * Show all captured patient data for final confirmation before submission.
 * Reuses #transcription-panel with a summary layout showing name, question, CNP, email.
 */
export function showConfirmationSummary(
  data: PatientData,
  onConfirm: () => void,
  onCancel: () => void,
): void {
  const panel = document.getElementById('transcription-panel');
  const indicator = document.getElementById('recording-indicator');
  const statusText = document.getElementById('status-text');
  const result = document.getElementById('transcription-result');
  const actions = document.getElementById('transcription-actions');
  const resultText = document.getElementById('result-text');
  const resultCnp = document.getElementById('result-cnp');
  const resultEmail = document.getElementById('result-email');

  if (panel) panel.classList.add('visible');
  if (indicator) indicator.classList.remove('active');
  if (statusText) statusText.textContent = RO.WORKFLOW_CONFIRM_ALL;

  // Build summary in result-text area
  const lines: string[] = [];
  if (data.name) lines.push(`${RO.WORKFLOW_NAME_LABEL}: ${data.name}`);
  if (data.question) lines.push(`${RO.WORKFLOW_QUESTION_LABEL}: ${data.question}`);
  if (data.phone) lines.push(`${RO.WORKFLOW_PHONE_LABEL}: ${data.phone}`);
  if (resultText) resultText.textContent = lines.join('\n');

  if (resultCnp) {
    resultCnp.textContent = data.cnp ? `${RO.CNP_LABEL}: ${data.cnp}` : '';
    resultCnp.style.display = data.cnp ? 'block' : 'none';
  }
  if (resultEmail) {
    resultEmail.textContent = data.email ? `${RO.EMAIL_LABEL}: ${data.email}` : '';
    resultEmail.style.display = data.email ? 'block' : 'none';
  }
  if (result) result.classList.add('visible');

  if (actions) {
    actions.innerHTML = '';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn-confirm';
    confirmBtn.textContent = RO.WORKFLOW_CONFIRM_SEND;
    confirmBtn.addEventListener('click', onConfirm, { once: true });

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-retry';
    cancelBtn.textContent = RO.WORKFLOW_CONFIRM_CANCEL;
    cancelBtn.addEventListener('click', onCancel, { once: true });

    actions.appendChild(confirmBtn);
    actions.appendChild(cancelBtn);
    actions.classList.add('visible');
  }
}

// ---------------------------------------------------------------------------
// Crash Alert
// ---------------------------------------------------------------------------

/**
 * Show crash alert overlay when detector unexpectedly stops.
 * Displays a Romanian message with a Restart button.
 */
export function showCrashAlert(onRestart: () => void): void {
  const alert = document.getElementById('crash-alert');
  const text = document.getElementById('crash-alert-text');
  const btn = document.getElementById('crash-restart-btn');

  if (text) text.textContent = RO.CRASH_ALERT;
  if (btn) {
    btn.textContent = RO.CRASH_RESTART;
    // Remove old listeners by cloning
    const newBtn = btn.cloneNode(true) as HTMLButtonElement;
    btn.parentNode?.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', onRestart, { once: true });
  }
  if (alert) alert.classList.add('visible');
}

/**
 * Hide the crash alert overlay.
 */
export function hideCrashAlert(): void {
  const alert = document.getElementById('crash-alert');
  if (alert) alert.classList.remove('visible');
}

// ---------------------------------------------------------------------------
// System Toggle Button
// ---------------------------------------------------------------------------

/**
 * Update the system toggle button text and state.
 */
export function updateSystemButton(running: boolean, transitioning?: boolean): void {
  const btn = document.getElementById('system-toggle-btn');
  if (!btn) return;
  if (transitioning) {
    btn.textContent = running ? RO.SYSTEM_STOPPING : RO.SYSTEM_STARTING;
    (btn as HTMLButtonElement).disabled = true;
  } else {
    btn.textContent = running ? RO.SYSTEM_STOP : RO.SYSTEM_START;
    (btn as HTMLButtonElement).disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Transcription Panel
// ---------------------------------------------------------------------------

/**
 * Hide the entire transcription panel. Resets all sub-elements.
 * Called after confirm/retry or workflow timeout.
 */
export function hideTranscriptionPanel(): void {
  const panel = document.getElementById('transcription-panel');
  const indicator = document.getElementById('recording-indicator');
  const statusText = document.getElementById('status-text');
  const result = document.getElementById('transcription-result');
  const actions = document.getElementById('transcription-actions');

  if (panel) panel.classList.remove('visible');
  if (indicator) indicator.classList.remove('active');
  if (statusText) statusText.textContent = '';
  if (result) result.classList.remove('visible');
  if (actions) {
    actions.classList.remove('visible');
    actions.innerHTML = '';
  }
}
