/**
 * Browser audio capture module.
 *
 * Provides mic initialization (inside user gesture), MediaRecorder
 * stop-and-collect recording, and transcription via backend API.
 *
 * AudioContext is created once on first initAudio() call and reused.
 * MediaStream tracks are released after every recording to avoid
 * lingering mic indicator.
 */

import { apiTranscribe } from './api.ts';
import type { TranscribeResult } from './types.ts';

export type { TranscribeResult };

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let audioCtx: AudioContext | null = null;
let micPermissionGranted = false;

const RECORD_DURATION_MS = 10_000;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Check whether the browser supports getUserMedia (secure context guard).
 * Returns false on insecure origins or older browsers.
 */
export function checkMicAvailability(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

/**
 * Create/resume AudioContext and request mic permission.
 *
 * MUST be called inside a user gesture handler (keydown, click) so that
 * AudioContext creation succeeds and the browser mic prompt appears.
 *
 * Requests a test getUserMedia stream and immediately releases it --
 * the actual recording stream is acquired in recordAndTranscribe().
 *
 * Returns true if mic permission was granted, false otherwise.
 */
export async function initAudio(): Promise<boolean> {
  // Create AudioContext once (user gesture required)
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }

  // Resume if suspended (browser policy)
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }

  // Request mic permission with a test stream
  try {
    const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // Immediately release -- we only wanted the permission grant
    testStream.getTracks().forEach((t) => t.stop());
    micPermissionGranted = true;
    return true;
  } catch (err) {
    console.warn('audio: mic permission denied or unavailable', err);
    micPermissionGranted = false;
    return false;
  }
}

/**
 * Returns whether mic permission has been granted via initAudio().
 */
export function isMicReady(): boolean {
  return micPermissionGranted;
}

/**
 * Record audio from the microphone and transcribe via backend.
 *
 * Uses the MediaRecorder stop-and-collect pattern:
 * 1. getUserMedia to get a fresh stream
 * 2. MediaRecorder.start() with no timeslice
 * 3. Wait for durationMs
 * 4. Stop recorder, collect blob from ondataavailable chunks
 * 5. Release mic tracks (no lingering indicator)
 * 6. POST blob to /api/transcribe via apiTranscribe
 *
 * @param durationMs  Recording duration in milliseconds (default 10s)
 * @param initialPrompt  Optional Whisper initial_prompt for improved accuracy
 * @returns Transcription result with text, cnp, email
 */
export async function recordAndTranscribe(
  durationMs: number = RECORD_DURATION_MS,
  initialPrompt?: string,
): Promise<TranscribeResult> {
  // 1. Acquire mic stream
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  // 2. Determine supported MIME type
  const preferredMime = 'audio/webm;codecs=opus';
  const mimeType = MediaRecorder.isTypeSupported(preferredMime)
    ? preferredMime
    : 'audio/webm';

  // 3. Create recorder (stop-and-collect -- no timeslice)
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];

  recorder.ondataavailable = (e: BlobEvent) => {
    if (e.data.size > 0) {
      chunks.push(e.data);
    }
  };

  recorder.start();

  // 4. Wait for recording duration
  await new Promise<void>((resolve) => setTimeout(resolve, durationMs));

  // 5. Stop recorder and wait for onstop (collects final chunk)
  const blob = await new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      // CRITICAL: Release mic tracks to remove lingering mic indicator
      stream.getTracks().forEach((t) => t.stop());
      resolve(new Blob(chunks, { type: mimeType }));
    };
    recorder.stop();
  });

  // 6. Transcribe via backend
  return apiTranscribe(blob, initialPrompt);
}
