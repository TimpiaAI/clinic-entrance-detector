/**
 * Patient workflow state machine — Form version.
 *
 * Two independent flows:
 *
 * 1. DETECTION: person enters → mp3 + form → submit → thank_you → idle
 * 2. CALL PATIENT: receptionist button → CHEAMAPACIENT.mp4 video → idle
 *
 * States: stopped → idle → form → form_submitting → thank_you → idle
 *                        → greeting (call patient video) → idle
 */

import { apiSubmitPatient } from './api.ts';
import type { EventLogEntry, WorkflowState } from './types.ts';
import { hideTranscriptionPanel } from './ui.ts';
import { hideVideo, hideMarquee, playSingleVideo } from './video.ts';

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

const THANK_YOU_DURATION = 6_000;
const FORM_TIMEOUT = 120_000;

// ---------------------------------------------------------------------------
//  Module-level state
// ---------------------------------------------------------------------------

let currentState: WorkflowState = 'stopped';
let stateTimeout: ReturnType<typeof setTimeout> | null = null;

// ---------------------------------------------------------------------------
//  DOM refs
// ---------------------------------------------------------------------------

function formOverlay(): HTMLElement | null {
  return document.getElementById('patient-form-overlay');
}

function thankYouOverlay(): HTMLElement | null {
  return document.getElementById('thank-you-overlay');
}

function patientForm(): HTMLFormElement | null {
  return document.getElementById('patient-form') as HTMLFormElement | null;
}

function greetingAudio(): HTMLAudioElement | null {
  return document.getElementById('greeting-audio') as HTMLAudioElement | null;
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

function clearStateTimeout(): void {
  if (stateTimeout !== null) {
    clearTimeout(stateTimeout);
    stateTimeout = null;
  }
}

function hideForm(): void {
  const overlay = formOverlay();
  if (overlay) overlay.classList.remove('visible');
}

function hideThankYou(): void {
  const overlay = thankYouOverlay();
  if (overlay) overlay.classList.remove('visible');
}

function resetForm(): void {
  const form = patientForm();
  if (form) form.reset();
}

function playGreeting(): void {
  const audio = greetingAudio();
  if (audio) {
    audio.currentTime = 0;
    audio.play().catch(() => {});
  }
}

function stopGreeting(): void {
  const audio = greetingAudio();
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
  }
}

function hideAll(): void {
  hideForm();
  hideThankYou();
  hideTranscriptionPanel();
  hideMarquee();
  hideVideo();
}

// ---------------------------------------------------------------------------
//  State machine
// ---------------------------------------------------------------------------

function transition(newState: WorkflowState): void {
  clearStateTimeout();
  const prevState = currentState;
  currentState = newState;
  console.log(`workflow: ${prevState} -> ${newState}`);
  executeStateEntry(newState);
}

function executeStateEntry(state: WorkflowState): void {
  switch (state) {
    case 'stopped':
      hideAll();
      break;

    case 'idle':
      hideAll();
      break;

    case 'form':
      executeForm();
      break;

    case 'form_submitting':
      executeFormSubmit();
      break;

    case 'thank_you':
      executeThankYou();
      break;

    case 'greeting':
      executeCallPatientVideo();
      break;

    default:
      break;
  }
}

// ---------------------------------------------------------------------------
//  FLOW 1: Detection → Form
// ---------------------------------------------------------------------------

function executeForm(): void {
  hideAll();

  const overlay = formOverlay();
  if (overlay) overlay.classList.add('visible');

  resetForm();
  playGreeting();

  const numeInput = document.getElementById('form-nume') as HTMLInputElement | null;
  if (numeInput) setTimeout(() => numeInput.focus(), 100);

  stateTimeout = setTimeout(() => {
    if (currentState === 'form') {
      console.warn('workflow: form timeout, returning to idle');
      stopGreeting();
      fetch('/api/form-abandoned', { method: 'POST' }).catch(() => {});
      transition('idle');
    }
  }, FORM_TIMEOUT);
}

function onFormSubmit(e: Event): void {
  e.preventDefault();
  if (currentState !== 'form') return;
  transition('form_submitting');
}

function executeFormSubmit(): void {
  const numeEl = document.getElementById('form-nume') as HTMLInputElement | null;
  const prenumeEl = document.getElementById('form-prenume') as HTMLInputElement | null;
  const emailEl = document.getElementById('form-email') as HTMLInputElement | null;
  const cnpEl = document.getElementById('form-cnp') as HTMLInputElement | null;
  const submitBtn = patientForm()?.querySelector('button[type="submit"]') as HTMLButtonElement | null;

  const nume = numeEl?.value.trim() || '';
  const prenume = prenumeEl?.value.trim() || '';
  const email = emailEl?.value.trim() || '';
  const cnp = cnpEl?.value.trim() || '';

  if (submitBtn) submitBtn.disabled = true;
  stopGreeting();

  const patientData = {
    name: `${prenume} ${nume}`.trim(),
    question: null,
    cnp: cnp || null,
    phone: null,
    email: email || null,
  };

  apiSubmitPatient(patientData)
    .then((response) => {
      if (currentState !== 'form_submitting') return;

      if (response.sign_url) {
        fetch('/api/sign-ready', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sign_url: response.sign_url }),
        }).catch(() => {});
      }

      transition('thank_you');
    })
    .catch((err: unknown) => {
      console.error('workflow: submit failed', err);
      if (currentState !== 'form_submitting') return;
      transition('thank_you');
    })
    .finally(() => {
      if (submitBtn) submitBtn.disabled = false;
    });
}

function executeThankYou(): void {
  hideForm();

  const overlay = thankYouOverlay();
  if (overlay) overlay.classList.add('visible');

  stateTimeout = setTimeout(() => {
    if (currentState === 'thank_you') {
      transition('idle');
    }
  }, THANK_YOU_DURATION);
}

// ---------------------------------------------------------------------------
//  FLOW 2: Call Patient → Video CHEAMAPACIENT.mp4
// ---------------------------------------------------------------------------

function executeCallPatientVideo(): void {
  hideAll();

  playSingleVideo('CHEAMAPACIENT.mp4', () => {
    // Video finished → notify receptie, back to idle (detection mode)
    fetch('/api/call-patient-done', { method: 'POST' }).catch(() => {});
    transition('idle');
  });
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

export function initWorkflow(): void {
  currentState = 'stopped';

  const form = patientForm();
  if (form) {
    form.addEventListener('submit', onFormSubmit);
  }
}

export function startWorkflow(): void {
  if (currentState !== 'stopped') return;
  transition('idle');
}

export function stopWorkflow(): void {
  clearStateTimeout();
  stopGreeting();
  hideAll();
  resetForm();
  currentState = 'stopped';
  console.log('workflow: stopped');
}

export function getWorkflowState(): WorkflowState {
  return currentState;
}

export function getPatientData(): Readonly<{ name: string | null; question: string | null; cnp: string | null; phone: string | null; email: string | null }> {
  return { name: null, question: null, cnp: null, phone: null, email: null };
}

export function onPersonEntered(): void {
  if (currentState === 'idle') {
    transition('form');
  }
}

// ---------------------------------------------------------------------------
//  Call-patient (receptionist button → play CHEAMAPACIENT.mp4)
// ---------------------------------------------------------------------------

let lastCallPatientTimestamp: string | null = null;

export function checkForCallPatient(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'call_patient');
  if (!latest) return;
  if (latest.timestamp === lastCallPatientTimestamp) return;

  lastCallPatientTimestamp = latest.timestamp;

  if (currentState === 'idle' || currentState === 'stopped') {
    if (currentState === 'stopped') currentState = 'idle';
    transition('greeting');
  }
  // If busy (form/thank_you), ignore — patient is already being served
}

// ---------------------------------------------------------------------------
//  Person-entered detection → show form
// ---------------------------------------------------------------------------

let lastPersonEnteredTimestamp: string | null = null;

export function checkForPersonEnteredWorkflow(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'person_entered' || e.event === 'signin_started');
  if (!latest) return;
  if (latest.timestamp === lastPersonEnteredTimestamp) return;

  lastPersonEnteredTimestamp = latest.timestamp;

  if (currentState === 'idle') {
    transition('form');
  } else if (currentState === 'stopped') {
    currentState = 'idle';
    transition('form');
  }
}
