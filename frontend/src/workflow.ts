/**
 * Patient workflow state machine — Form version.
 *
 * When a person is detected entering, a keyboard form is shown
 * (Nume, Prenume, Email, CNP) with ava_greeting.mp3 playing in background.
 * After submission, a thank-you message is displayed for a few seconds,
 * then the system returns to idle.
 *
 * States: stopped → idle → form → form_submitting → thank_you → idle
 */

import { apiSubmitPatient } from './api.ts';
import type { EventLogEntry, WorkflowState } from './types.ts';
import { hideTranscriptionPanel } from './ui.ts';
import { hideVideo, hideMarquee } from './video.ts';

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

/** How long the thank-you screen stays visible (ms). */
const THANK_YOU_DURATION = 6_000;

/** Form timeout — auto-reset if nobody submits (ms). */
const FORM_TIMEOUT = 120_000;

// ---------------------------------------------------------------------------
//  Module-level state
// ---------------------------------------------------------------------------

let currentState: WorkflowState = 'stopped';
let stateTimeout: ReturnType<typeof setTimeout> | null = null;

// ---------------------------------------------------------------------------
//  DOM refs (resolved lazily)
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
//  Core helpers
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
    audio.play().catch(() => {
      // Autoplay may be blocked before user gesture — silently ignore
    });
  }
}

function stopGreeting(): void {
  const audio = greetingAudio();
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
  }
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
      hideForm();
      hideThankYou();
      hideTranscriptionPanel();
      hideMarquee();
      hideVideo();
      break;

    case 'idle':
      hideForm();
      hideThankYou();
      hideTranscriptionPanel();
      hideMarquee();
      hideVideo();
      // Drain queue
      if (callPatientQueue > 0) {
        callPatientQueue--;
        setTimeout(() => {
          if (currentState === 'idle') transition('form');
        }, 2000);
      }
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

    default:
      // Legacy states from video workflow — ignore in Form version
      break;
  }
}

// ---------------------------------------------------------------------------
//  Form state
// ---------------------------------------------------------------------------

function executeForm(): void {
  // Hide video, show form
  hideVideo();
  hideMarquee();
  hideTranscriptionPanel();

  const overlay = formOverlay();
  if (overlay) overlay.classList.add('visible');

  resetForm();

  // Play greeting audio in background
  playGreeting();

  // Focus first field
  const numeInput = document.getElementById('form-nume') as HTMLInputElement | null;
  if (numeInput) setTimeout(() => numeInput.focus(), 100);

  // Timeout — return to idle if nobody submits
  stateTimeout = setTimeout(() => {
    if (currentState === 'form') {
      console.warn('workflow: form timeout, returning to idle');
      stopGreeting();
      // Notify backend so receptie resets
      fetch('/api/form-abandoned', { method: 'POST' }).catch(() => {});
      transition('idle');
    }
  }, FORM_TIMEOUT);
}

/** Called when patient form is submitted. */
function onFormSubmit(e: Event): void {
  e.preventDefault();
  if (currentState !== 'form') return;

  transition('form_submitting');
}

// ---------------------------------------------------------------------------
//  Submit state
// ---------------------------------------------------------------------------

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

  // Disable button during submission
  if (submitBtn) submitBtn.disabled = true;

  stopGreeting();

  // Build patient data compatible with existing backend
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

      // If sign_url returned, notify receptie
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
      // Still show thank you even if backend fails
      transition('thank_you');
    })
    .finally(() => {
      if (submitBtn) submitBtn.disabled = false;
    });
}

// ---------------------------------------------------------------------------
//  Thank you state
// ---------------------------------------------------------------------------

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
//  Public API
// ---------------------------------------------------------------------------

export function initWorkflow(): void {
  currentState = 'stopped';

  // Wire form submit handler
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
  hideForm();
  hideThankYou();
  hideTranscriptionPanel();
  hideMarquee();
  hideVideo();
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
//  Call-patient queue
// ---------------------------------------------------------------------------

let callPatientQueue = 0;
let lastCallPatientTimestamp: string | null = null;

export function checkForCallPatient(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'call_patient');
  if (!latest) return;
  if (latest.timestamp === lastCallPatientTimestamp) return;

  lastCallPatientTimestamp = latest.timestamp;

  if (currentState === 'idle' || currentState === 'stopped') {
    // In form version, just start the form workflow
    if (currentState === 'stopped') currentState = 'idle';
    transition('form');
  }
}

// ---------------------------------------------------------------------------
//  Person-entered detection
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
  } else {
    callPatientQueue++;
    console.log(`workflow: person_entered queued (queue=${callPatientQueue})`);
  }
}
