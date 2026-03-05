/**
 * Video playback module — single-element src-swap pattern.
 *
 * Manages the #video-overlay element with three states: idle (loop video1.mp4),
 * playing_sequence (instructional videos in order), and hidden (no playback).
 *
 * Uses addEventListener('ended') for sequence transitions — never timers.
 * Single video element reuse avoids Chromium memory leak (crbug.com/41462045).
 */

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

// ---------------------------------------------------------------------------
//  State
// ---------------------------------------------------------------------------

export type VideoState = 'idle' | 'playing_sequence' | 'hidden';

let state: VideoState = 'hidden';
let sequenceIndex = 0;
let userGestureReceived = false;

/** Resolved once by initVideo(). */
let videoEl: HTMLVideoElement | null = null;

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
 */
function playNextInSequence(): void {
  if (sequenceIndex >= INSTRUCTION_SEQUENCE.length) {
    startIdleLoop();
    return;
  }

  const filename = INSTRUCTION_SEQUENCE[sequenceIndex];
  sequenceIndex++;
  playVideo(filename, { loop: false });
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
 */
export function startIdleLoop(): void {
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
