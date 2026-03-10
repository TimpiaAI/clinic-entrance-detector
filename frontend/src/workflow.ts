/**
 * Patient workflow state machine.
 *
 * Orchestrates the full patient interaction cycle: idle -> greeting ->
 * ask_name -> recording_name -> show_name -> ... -> confirm_all ->
 * submitting -> farewell -> farewell_idle -> final -> idle.
 *
 * Uses playSingleVideo() for individual video playback (not the linear
 * instruction sequence from Phase 3). Each recording state calls
 * recordAndTranscribe() from audio.ts and shows results via ui.ts.
 *
 * Timeout on any state clears patient data and returns to idle.
 * Emergency stop (Escape) aborts active recordings and transitions to stopped.
 */

import { apiSubmitPatient } from './api.ts';
import { recordAndTranscribe, onInterimTranscript } from './audio.ts';
import type { EventLogEntry, PatientData, TranscribeResult, WorkflowState } from './types.ts';
import {
  hideTranscriptionPanel,
  showConfirmationSummary,
  showProcessingState,
  showRecordingState,
  showTranscriptionResult,
  updateRecordingInterim,
  showEditableField,
  updateEditableField,
  getEditableFieldValue,
  hideEditableField,
} from './ui.ts';
import { hideVideo, playSingleVideo, showMarquee, hideMarquee, startIdleLoop } from './video.ts';
import { RO } from './ro.ts';

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

/** Timeout durations per state (milliseconds). */
const STATE_TIMEOUTS: Partial<Record<WorkflowState, number>> = {
  greeting: 60_000,
  ask_name: 60_000,
  recording_name: 50_000,       // 30s max record + 20s buffer for transcription
  show_name: 30_000,
  ask_question: 60_000,
  recording_question: 50_000,
  show_question: 30_000,
  ask_cnp: 60_000,
  recording_cnp: 50_000,
  show_cnp: 30_000,
  ask_email: 60_000,
  recording_email: 50_000,
  show_email: 30_000,
  confirm_all: 60_000,
  submitting: 30_000,
  farewell: 60_000,
  farewell_idle: 6_000,         // 5s idle + 1s buffer
  final: 60_000,
};

/** Recording prompts from controller.py. */
const RECORDING_PROMPTS: Record<string, string | undefined> = {
  recording_name: undefined,
  recording_question: undefined,
  recording_cnp: '1 2 3 4 5 6 7 8 9 1 2 3 4',
  recording_email: 'tudor.trocaru arond gmail punct com, radu.popescu arond yahoo punct com, ion.ionescu arond gmail punct com',
};

/** Video filenames for each state. */
const STATE_VIDEOS: Partial<Record<WorkflowState, string>> = {
  greeting: 'video2.mp4',
  ask_name: 'video3.mp4',
  ask_question: 'video6.mp4',
  ask_cnp: 'video7.mp4',
  ask_email: 'video8.mp4',
  farewell: 'video4.mp4',
  final: 'video5.mp4',
};

/** Marquee labels for video states. */
const STATE_MARQUEES: Partial<Record<WorkflowState, string>> = {
  greeting: RO.VIDEO_GREETING,
  ask_name: RO.VIDEO_ASK_NAME,
  ask_question: RO.VIDEO_ASK_QUESTION,
  ask_cnp: RO.VIDEO_ASK_CNP,
  ask_email: RO.VIDEO_ASK_EMAIL,
  farewell: RO.VIDEO_FAREWELL,
  final: RO.VIDEO_FINAL,
};

// ---------------------------------------------------------------------------
//  Module-level state
// ---------------------------------------------------------------------------

let currentState: WorkflowState = 'stopped';
let patientData: PatientData = { name: null, question: null, cnp: null, email: null };
let stateTimeout: ReturnType<typeof setTimeout> | null = null;

/**
 * Cancellation flag for active recordings. When set to true, recording
 * results are discarded after the Promise resolves. We cannot truly abort
 * a MediaRecorder from outside, but we can ignore the result.
 */
let recordingCancelled = false;

/** Flag indicating a recording is in progress (for abort/timeout). */
let recordingActive = false;

// ---------------------------------------------------------------------------
//  Core state machine
// ---------------------------------------------------------------------------

/**
 * Transition to a new workflow state.
 * Clears any active timeout, sets the new state, starts a state-specific
 * timeout, and executes the entry action for the new state.
 */
function transition(newState: WorkflowState): void {
  if (stateTimeout !== null) {
    clearTimeout(stateTimeout);
    stateTimeout = null;
  }

  const prevState = currentState;
  currentState = newState;
  console.log(`workflow: ${prevState} -> ${newState}`);

  // Start state-specific timeout (if defined)
  const timeout = STATE_TIMEOUTS[newState];
  if (timeout !== undefined) {
    stateTimeout = setTimeout(() => handleTimeout(), timeout);
  }

  // Execute entry action
  executeStateEntry(newState);
}

/**
 * Handle timeout -- abort active recording, clear data, return to idle.
 */
function handleTimeout(): void {
  console.warn(`workflow: timeout in state ${currentState}`);

  // Cancel any active recording
  if (recordingActive) {
    recordingCancelled = true;
  }

  // Clear patient data
  resetPatientData();

  // Hide UI
  hideTranscriptionPanel();
  hideMarquee();

  // Return to idle
  transition('idle');
}

/** Reset patient data to empty. */
function resetPatientData(): void {
  patientData = { name: null, question: null, cnp: null, email: null };
}

// ---------------------------------------------------------------------------
//  State entry actions
// ---------------------------------------------------------------------------

/**
 * Execute the entry action for a given state. This is the central
 * dispatcher that orchestrates video, recording, and UI for each state.
 */
function executeStateEntry(state: WorkflowState): void {
  switch (state) {
    case 'stopped':
      break;

    case 'idle':
      hideTranscriptionPanel();
      hideMarquee();
      startIdleLoop();
      break;

    case 'greeting':
    case 'ask_name':
    case 'ask_question':
    case 'ask_cnp':
    case 'ask_email':
    case 'farewell':
    case 'final':
      executeVideoState(state);
      break;

    case 'recording_name':
    case 'recording_question':
    case 'recording_cnp':
    case 'recording_email':
      executeRecordingState(state);
      break;

    case 'show_name':
    case 'show_question':
    case 'show_cnp':
    case 'show_email':
      // show_* states immediately advance to the next ask/confirm step
      executeShowStateTransition(state);
      break;

    case 'confirm_all':
      executeConfirmAll();
      break;

    case 'submitting':
      executeSubmitting();
      break;

    case 'farewell_idle':
      executeFarewellIdle();
      break;
  }
}

// ---------------------------------------------------------------------------
//  Video states
// ---------------------------------------------------------------------------

/**
 * Play a single video for a state and transition to the next state on ended.
 */
function executeVideoState(state: WorkflowState): void {
  const video = STATE_VIDEOS[state];
  if (!video) return;

  const marquee = STATE_MARQUEES[state];
  if (marquee) {
    showMarquee(marquee);
  } else {
    hideMarquee();
  }

  playSingleVideo(video, () => {
    hideMarquee();
    transitionAfterVideo(state);
  });
}

/**
 * Determine the next state after a video finishes playing.
 */
function transitionAfterVideo(state: WorkflowState): void {
  switch (state) {
    case 'greeting':
      transition('ask_name');
      break;
    case 'ask_name':
      transition('recording_name');
      break;
    case 'ask_question':
      transition('recording_question');
      break;
    case 'ask_cnp':
      transition('recording_cnp');
      break;
    case 'ask_email':
      transition('recording_email');
      break;
    case 'farewell':
      transition('farewell_idle');
      break;
    case 'final':
      transition('idle');
      break;
  }
}

// ---------------------------------------------------------------------------
//  Recording states
// ---------------------------------------------------------------------------

/**
 * Execute a recording state: show recording UI, start idle video loop,
 * record audio, transcribe, show result with confirm/retry.
 */
function executeRecordingState(state: WorkflowState): void {
  // Start idle video as background during recording
  startIdleLoop();

  // Show recording indicator immediately
  showRecordingState();

  const prompt = RECORDING_PROMPTS[state];
  recordingCancelled = false;
  recordingActive = true;

  // For CNP and email: show editable input field
  const isEditable = state === 'recording_cnp' || state === 'recording_email';
  if (isEditable) {
    const label = state === 'recording_cnp' ? RO.CNP_LABEL : RO.EMAIL_LABEL;
    showEditableField(label);
  }

  // Show live interim text as user speaks
  onInterimTranscript((text) => {
    updateRecordingInterim(text);
    if (isEditable) {
      // Extract digits for CNP, or clean email attempt
      if (state === 'recording_cnp') {
        const digits = text.replace(/[^0-9]/g, '');
        if (digits) updateEditableField(digits);
      } else {
        updateEditableField(text);
      }
    }
  });

  recordAndTranscribe(10_000, prompt)
    .then((result: TranscribeResult) => {
      recordingActive = false;

      // Check if recording was cancelled (timeout or emergency stop)
      if (recordingCancelled) {
        recordingCancelled = false;
        hideEditableField();
        return;
      }

      // Check we are still in the expected state (guard against race)
      if (currentState !== state) {
        hideEditableField();
        return;
      }

      // For editable fields, override result with field value
      if (isEditable) {
        const fieldValue = getEditableFieldValue();
        if (fieldValue) {
          if (state === 'recording_cnp') {
            result = { ...result, text: fieldValue, cnp: fieldValue };
          } else {
            result = { ...result, text: fieldValue, email: fieldValue };
          }
        }
        hideEditableField();
      }

      showProcessingState();

      // Determine the show_* state and data field
      const { showState, dataField } = recordingStateMapping(state);

      // Show transcription result with confirm/retry
      showTranscriptionResult(result, () => {
        // On confirm: store data and advance
        storeRecordingResult(dataField, result);
        hideTranscriptionPanel();
        transition(showState);
      }, () => {
        // On retry: re-record
        hideTranscriptionPanel();
        transition(state);
      });
    })
    .catch((err: unknown) => {
      recordingActive = false;
      hideEditableField();
      console.error('workflow: recording failed', err);

      // On error, show empty result with retry option
      if (currentState !== state) return;
      if (recordingCancelled) {
        recordingCancelled = false;
        return;
      }

      showTranscriptionResult({ text: '', cnp: null, email: null }, () => {
        hideTranscriptionPanel();
        const { showState, dataField } = recordingStateMapping(state);
        storeRecordingResult(dataField, { text: '', cnp: null, email: null });
        transition(showState);
      }, () => {
        hideTranscriptionPanel();
        transition(state);
      });
    });
}

/**
 * Map a recording state to its corresponding show state and patient data field.
 */
function recordingStateMapping(state: WorkflowState): {
  showState: WorkflowState;
  dataField: keyof PatientData;
} {
  switch (state) {
    case 'recording_name':
      return { showState: 'show_name', dataField: 'name' };
    case 'recording_question':
      return { showState: 'show_question', dataField: 'question' };
    case 'recording_cnp':
      return { showState: 'show_cnp', dataField: 'cnp' };
    case 'recording_email':
      return { showState: 'show_email', dataField: 'email' };
    default:
      return { showState: 'idle', dataField: 'name' };
  }
}

/**
 * Store a recording result in the appropriate patient data field.
 */
function storeRecordingResult(field: keyof PatientData, result: TranscribeResult): void {
  switch (field) {
    case 'name':
      patientData.name = result.text || null;
      break;
    case 'question':
      patientData.question = result.text || null;
      break;
    case 'cnp':
      patientData.cnp = result.cnp || result.text || null;
      break;
    case 'email':
      patientData.email = result.email || result.text || null;
      break;
  }
}

// ---------------------------------------------------------------------------
//  Show states -> next transitions
// ---------------------------------------------------------------------------

/**
 * The show_* states immediately transition to the next ask/confirm state.
 * Data was already stored by the recording confirm callback.
 */
function executeShowStateTransition(state: WorkflowState): void {
  switch (state) {
    case 'show_name':
      transition('ask_question');
      break;
    case 'show_question':
      transition('ask_cnp');
      break;
    case 'show_cnp':
      transition('ask_email');
      break;
    case 'show_email':
      transition('confirm_all');
      break;
  }
}

// ---------------------------------------------------------------------------
//  Confirm all + Submit
// ---------------------------------------------------------------------------

/**
 * Show the confirmation summary with all patient data.
 */
function executeConfirmAll(): void {
  showConfirmationSummary(
    patientData,
    () => {
      // On confirm: submit
      hideTranscriptionPanel();
      transition('submitting');
    },
    () => {
      // On cancel: clear and return to idle
      hideTranscriptionPanel();
      resetPatientData();
      transition('idle');
    },
  );
}

/**
 * Submit patient data to the backend.
 */
function executeSubmitting(): void {
  apiSubmitPatient(patientData)
    .then(() => {
      if (currentState !== 'submitting') return;
      transition('farewell');
    })
    .catch((err: unknown) => {
      console.error('workflow: submit failed', err);
      if (currentState !== 'submitting') return;
      // On failure, return to idle (data is lost -- acceptable for v1)
      transition('idle');
    });
}

// ---------------------------------------------------------------------------
//  Farewell idle (video1 loop for 5 seconds)
// ---------------------------------------------------------------------------

function executeFarewellIdle(): void {
  hideMarquee();
  startIdleLoop();
  // The state timeout (6s) will fire and we transition manually to final
  // Override the timeout handler for this specific state
  if (stateTimeout !== null) {
    clearTimeout(stateTimeout);
  }
  stateTimeout = setTimeout(() => {
    if (currentState === 'farewell_idle') {
      transition('final');
    }
  }, 5_000);
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

/**
 * Initialize the workflow module. Sets initial state to stopped.
 */
export function initWorkflow(): void {
  currentState = 'stopped';
  resetPatientData();
}

/**
 * Start the workflow. Transitions from stopped to idle (starts idle video loop).
 */
export function startWorkflow(): void {
  if (currentState !== 'stopped') return;
  transition('idle');
}

/**
 * Stop the workflow. Abort any active recording, clear data,
 * transition to stopped, hide video and transcription panel.
 */
export function stopWorkflow(): void {
  // Cancel active recording
  if (recordingActive) {
    recordingCancelled = true;
  }

  // Clear timeout
  if (stateTimeout !== null) {
    clearTimeout(stateTimeout);
    stateTimeout = null;
  }

  // Clear data
  resetPatientData();

  // Hide everything
  hideTranscriptionPanel();
  hideMarquee();
  hideVideo();

  currentState = 'stopped';
  console.log('workflow: stopped');
}

/**
 * Returns the current workflow state.
 */
export function getWorkflowState(): WorkflowState {
  return currentState;
}

/**
 * Returns a read-only copy of the patient data.
 */
export function getPatientData(): Readonly<PatientData> {
  return { ...patientData };
}

/**
 * Handle a person_entered event. If in idle state, transition to greeting.
 * Otherwise ignore (workflow already active for current patient).
 */
export function onPersonEntered(): void {
  if (currentState === 'idle') {
    transition('greeting');
  }
}

// ---------------------------------------------------------------------------
//  Person-entered detection (event log diffing for workflow)
// ---------------------------------------------------------------------------

/** Timestamp of the last person_entered event processed by the workflow. */
let lastWorkflowPersonTimestamp: string | null = null;

/**
 * Check the event log for a new person_entered event and call onPersonEntered().
 * Mirrors the timestamp-diffing pattern from video.ts but routes to the workflow
 * state machine instead of the linear instruction sequence.
 *
 * Called from main.ts setOnStateUpdate callback on every WebSocket snapshot.
 */
export function checkForPersonEnteredWorkflow(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'person_entered');
  if (!latest) return;
  if (latest.timestamp === lastWorkflowPersonTimestamp) return;

  lastWorkflowPersonTimestamp = latest.timestamp;
  onPersonEntered(); // Guards internally: only acts if workflow is in 'idle' state
}
