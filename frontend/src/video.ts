/**
 * Video playback module — single-element src-swap pattern.
 *
 * Manages the #video-overlay element with three states: idle (loop video1.mp4),
 * playing_sequence (instructional videos in order), and hidden (no playback).
 *
 * Uses addEventListener('ended') for sequence transitions — never timers.
 * Single video element reuse avoids Chromium memory leak (crbug.com/41462045).
 *
 * Person-entered detection via event log timestamp diffing triggers the
 * instructional sequence automatically. Marquee text overlays show Romanian
 * labels during each video in the sequence.
 */

import { RO } from './ro.ts';
import type { EventLogEntry } from './types.ts';

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

const IDLE_VIDEO = 'video1.mp4';

/** Exact sequence from controller.py workflow() */
const INSTRUCTION_SEQUENCE = [
  'video2.mp4', // greeting
  'video3.mp4', // ask name
  'video6.mp4', // ask (question)
  'video7.mp4', // ask CNP
  'video8.mp4', // ask email
  'video4.mp4', // farewell
  'video5.mp4', // final
];

/** Maps each instructional video to its Romanian marquee label. */
const VIDEO_LABELS: Record<string, string> = {
  'video2.mp4': RO.VIDEO_GREETING,
  'video3.mp4': RO.VIDEO_ASK_NAME,
  'video6.mp4': RO.VIDEO_ASK_QUESTION,
  'video7.mp4': RO.VIDEO_ASK_CNP,
  'video8.mp4': RO.VIDEO_ASK_EMAIL,
  'video4.mp4': RO.VIDEO_FAREWELL,
  'video5.mp4': RO.VIDEO_FINAL,
};

// ---------------------------------------------------------------------------
//  State
// ---------------------------------------------------------------------------

export type VideoState = 'idle' | 'playing_sequence' | 'hidden';

let state: VideoState = 'hidden';
let sequenceIndex = 0;
let userGestureReceived = false;

/** Timestamp of the last person_entered event we processed. */
let lastPersonEnteredTimestamp: string | null = null;

/** Resolved once by initVideo(). */
let videoEl: HTMLVideoElement | null = null;
let textOverlayEl: HTMLElement | null = null;
let marqueeContentEl: HTMLElement | null = null;

// ---------------------------------------------------------------------------
//  Internal helpers
// ---------------------------------------------------------------------------

/**
 * Set src on the single video element, load, show, and play.
 * Never creates/destroys elements — reuses #video-overlay.
 */
async function playVideo(
  filename: string,
  opts?: { loop?: boolean },
): Promise<void> {
  if (!videoEl) return;

  videoEl.loop = opts?.loop ?? false;
  videoEl.src = `/api/videos/${filename}`;
  videoEl.load();
  videoEl.style.opacity = '1';

  try {
    await videoEl.play();
  } catch (err: unknown) {
    // NotAllowedError is expected before user gesture — video stays muted
    if (err instanceof DOMException && err.name === 'NotAllowedError') {
      console.warn('video: autoplay blocked — waiting for user gesture');
    } else {
      console.error('video: playback error', err);
    }
  }
}

/**
 * Play the next video in the instruction sequence, or return to idle.
 * Shows the corresponding Romanian marquee label for each video.
 */
function playNextInSequence(): void {
  if (sequenceIndex >= INSTRUCTION_SEQUENCE.length) {
    startIdleLoop();
    return;
  }

  const filename = INSTRUCTION_SEQUENCE[sequenceIndex];
  sequenceIndex++;
  playVideo(filename, { loop: false });

  const label = VIDEO_LABELS[filename];
  if (label) {
    showMarquee(label);
  } else {
    hideMarquee();
  }
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

/**
 * Initialize the video module. Must be called once on DOMContentLoaded.
 * Wires the 'ended' event for sequence transitions.
 */
export function initVideo(): void {
  videoEl = document.getElementById('video-overlay') as HTMLVideoElement | null;
  textOverlayEl = document.getElementById('text-overlay');
  marqueeContentEl = textOverlayEl?.querySelector('.marquee-content') ?? null;

  if (!videoEl) {
    console.error('video: #video-overlay element not found');
    return;
  }

  videoEl.addEventListener('ended', () => {
    if (state === 'playing_sequence') {
      playNextInSequence();
    }
  });
}

/**
 * Start the idle loop — plays video1.mp4 with loop=true.
 * onended does NOT fire when loop=true (MDN confirmed), so idle is stable.
 * Hides marquee text overlay when returning to idle.
 */
export function startIdleLoop(): void {
  hideMarquee();
  state = 'idle';
  sequenceIndex = 0;
  playVideo(IDLE_VIDEO, { loop: true });
}

/**
 * Start the instructional video sequence (video2 -> video3 -> video6 ->
 * video7 -> video8 -> video4 -> video5). Guarded against re-trigger
 * during active sequence.
 */
export function startInstructionSequence(): void {
  if (state === 'playing_sequence') return;
  state = 'playing_sequence';
  sequenceIndex = 0;
  playNextInSequence();
}

/**
 * Hide the video overlay. Releases buffered data per W3C spec
 * (remove src + call load()).
 */
export function hideVideo(): void {
  state = 'hidden';
  if (!videoEl) return;
  videoEl.style.opacity = '0';
  videoEl.pause();
  videoEl.removeAttribute('src');
  videoEl.load();
}

/**
 * Capture first user gesture to unmute video.
 * Called from F2 handler so operator's first keypress enables audio.
 */
export function onUserGesture(): void {
  if (userGestureReceived) return;
  userGestureReceived = true;
  if (videoEl) {
    videoEl.muted = false;
  }
}

/** Returns current video playback state. */
export function getVideoState(): VideoState {
  return state;
}

// ---------------------------------------------------------------------------
//  Person-entered detection (event log diffing)
// ---------------------------------------------------------------------------

/**
 * Check the event log for a new person_entered event and trigger the
 * instructional video sequence if found.
 *
 * The event_log array is newest-first (Python deque appendleft). We compare
 * the latest person_entered timestamp against our tracked value. Timestamp
 * comparison naturally handles WebSocket reconnects — stale logs re-sent
 * after reconnect have the same timestamp, so no phantom trigger occurs.
 *
 * Called from setOnStateUpdate callback on every WebSocket snapshot (~0.5s).
 */
export function checkForPersonEntered(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'person_entered');
  if (!latest) return;
  if (latest.timestamp === lastPersonEnteredTimestamp) return;

  lastPersonEnteredTimestamp = latest.timestamp;
  startInstructionSequence(); // Guard inside prevents re-trigger during active sequence
}

// ---------------------------------------------------------------------------
//  Marquee text overlay
// ---------------------------------------------------------------------------

/**
 * Show the marquee text overlay with the given text.
 * Updates the .marquee-content span and fades in the #text-overlay container.
 */
export function showMarquee(text: string): void {
  if (marqueeContentEl) {
    marqueeContentEl.textContent = text;
  }
  if (textOverlayEl) {
    textOverlayEl.style.opacity = '1';
  }
}

/**
 * Hide the marquee text overlay by fading out the #text-overlay container.
 */
export function hideMarquee(): void {
  if (textOverlayEl) {
    textOverlayEl.style.opacity = '0';
  }
}
