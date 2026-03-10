/**
 * Browser audio capture with Deepgram real-time streaming transcription.
 *
 * Streams mic audio via WebSocket to backend proxy -> Deepgram.
 * Receives interim + final results live. Deepgram's utterance_end
 * detection signals when the speaker has stopped.
 *
 * Falls back to batch upload if streaming fails.
 */

import { apiTranscribe } from './api.ts';
import type { TranscribeResult } from './types.ts';

export type { TranscribeResult };

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let audioCtx: AudioContext | null = null;
let micPermissionGranted = false;

/** Safety cap for streaming recording (ms). */
const MAX_STREAM_MS = 20_000;

// ---------------------------------------------------------------------------
// Callback for live interim text updates
// ---------------------------------------------------------------------------

type InterimCallback = (text: string) => void;
let _onInterim: InterimCallback | null = null;

/**
 * Register a callback to receive live interim transcription text.
 * Called from workflow.ts to update UI in real-time as user speaks.
 */
export function onInterimTranscript(cb: InterimCallback): void {
  _onInterim = cb;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function checkMicAvailability(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

export async function initAudio(): Promise<boolean> {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }
  try {
    const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    testStream.getTracks().forEach((t) => t.stop());
    micPermissionGranted = true;
    return true;
  } catch (err) {
    console.warn('audio: mic permission denied or unavailable', err);
    micPermissionGranted = false;
    return false;
  }
}

export function isMicReady(): boolean {
  return micPermissionGranted;
}

/**
 * Record and transcribe using Deepgram real-time streaming.
 *
 * Opens a WebSocket to /ws/transcribe, streams PCM16 audio from mic,
 * receives interim results (shown live) and waits for utterance_end
 * to finalize. Returns the final transcript.
 */
export async function recordAndTranscribe(
  _durationMs?: number,
  _initialPrompt?: string,
): Promise<TranscribeResult> {
  // Ensure AudioContext
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }

  // Acquire mic
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  try {
    return await streamTranscribe(stream);
  } catch (err) {
    console.warn('audio: streaming failed, falling back to batch', err);
    return batchTranscribe(stream, _initialPrompt);
  }
}

// ---------------------------------------------------------------------------
// Streaming implementation
// ---------------------------------------------------------------------------

function streamTranscribe(stream: MediaStream): Promise<TranscribeResult> {
  return new Promise((resolve, reject) => {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws/transcribe`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    let finalText = '';
    let lastInterim = '';
    let resolved = false;
    let speechHeard = false;

    // AudioContext for resampling to 16kHz PCM16
    const ctx = new AudioContext({ sampleRate: 16000 });
    const source = ctx.createMediaStreamSource(stream);

    // ScriptProcessor to capture raw PCM (4096 samples per chunk)
    const processor = ctx.createScriptProcessor(4096, 1, 1);

    function cleanup() {
      try { processor.disconnect(); } catch {}
      try { source.disconnect(); } catch {}
      try { ctx.close(); } catch {}
      stream.getTracks().forEach((t) => t.stop());
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    }

    // Safety timeout
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        cleanup();
        resolve(buildResult(finalText || lastInterim));
      }
    }, MAX_STREAM_MS);

    ws.onopen = () => {
      console.log('audio: streaming WS connected');
      source.connect(processor);
      processor.connect(ctx.destination);

      // Send PCM16 audio chunks
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        ws.send(int16.buffer);
      };
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'transcript') {
          const text = msg.text || '';

          if (msg.is_final && text) {
            finalText += (finalText ? ' ' : '') + text;
            speechHeard = true;
            if (_onInterim) _onInterim(finalText);
          } else if (text) {
            lastInterim = text;
            speechHeard = true;
            if (_onInterim) _onInterim(finalText + (finalText ? ' ' : '') + text);
          }
        }

        if (msg.type === 'utterance_end' && speechHeard) {
          // Speaker stopped — finalize
          if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            cleanup();
            resolve(buildResult(finalText || lastInterim));
          }
        }
      } catch {}
    };

    ws.onerror = (err) => {
      console.error('audio: streaming WS error', err);
      if (!resolved) {
        resolved = true;
        clearTimeout(timeout);
        cleanup();
        reject(err);
      }
    };

    ws.onclose = () => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timeout);
        cleanup();
        resolve(buildResult(finalText || lastInterim));
      }
    };
  });
}

// ---------------------------------------------------------------------------
// Batch fallback (old approach)
// ---------------------------------------------------------------------------

async function batchTranscribe(
  stream: MediaStream,
  initialPrompt?: string,
): Promise<TranscribeResult> {
  const preferredMime = 'audio/webm;codecs=opus';
  const mimeType = MediaRecorder.isTypeSupported(preferredMime)
    ? preferredMime
    : 'audio/webm';

  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];

  recorder.ondataavailable = (e: BlobEvent) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  recorder.start();

  // Simple 8-second recording for fallback
  await new Promise<void>((resolve) => setTimeout(resolve, 8000));

  const blob = await new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      resolve(new Blob(chunks, { type: mimeType }));
    };
    recorder.stop();
  });

  return apiTranscribe(blob, initialPrompt);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildResult(text: string): TranscribeResult {
  return {
    text,
    cnp: extractCnp(text),
    email: extractEmail(text),
  };
}

function extractCnp(text: string): string | null {
  const digits = text.replace(/[^0-9]/g, '');
  if (digits.length >= 13) return digits.slice(0, 13);
  if (digits.length >= 10) return digits;
  return null;
}

function extractEmail(text: string): string | null {
  let attempt = text.toLowerCase();
  attempt = attempt.replace(/\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)/g, '.$2');
  attempt = attempt.replace(/\s*(a rung|a run|arond|arong|aroon|arun|arung|@)\s*/g, '@');
  attempt = attempt.replace(/\b(at|et|ad)\b/g, '@');

  if (!attempt.includes('@')) return null;
  const lastAt = attempt.lastIndexOf('@');
  const domain = attempt.slice(lastAt + 1).replace(/\s/g, '').replace(/^\./, '');
  if (!domain.includes('.')) return null;

  const localTokens = attempt.slice(0, lastAt).trim().split(/\s+/);
  const local = (localTokens[localTokens.length - 1] || '').replace(/\s/g, '').replace(/\.$/, '');
  if (!local || !domain) return null;

  return (local + '@' + domain).replace(/[^a-z0-9@._\-]/g, '') || null;
}
