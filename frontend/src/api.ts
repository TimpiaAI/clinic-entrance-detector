/**
 * REST API call wrappers for backend endpoints.
 *
 * All functions use relative URLs so Vite proxy works in dev
 * and same-origin works in production.
 */

import type { TranscribeResult } from './types.ts';

interface StartResponse {
  status: string;
  pid?: number;
}

interface StopResponse {
  status: string;
}

interface StatusResponse {
  running: boolean;
  pid: number | null;
  exit_code: number | null;
}

interface WebhookResponse {
  status: string;
  payload?: Record<string, unknown>;
}

interface WakeLockResponse {
  status: string;
}

async function post<T>(url: string): Promise<T> {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return (await res.json()) as T;
  } catch (err) {
    console.error(`api: POST ${url} failed`, err);
    throw err;
  }
}

async function get<T>(url: string): Promise<T> {
  try {
    const res = await fetch(url);
    return (await res.json()) as T;
  } catch (err) {
    console.error(`api: GET ${url} failed`, err);
    throw err;
  }
}

export function apiStartDetector(): Promise<StartResponse> {
  return post<StartResponse>('/api/process/start');
}

export function apiStopDetector(): Promise<StopResponse> {
  return post<StopResponse>('/api/process/stop');
}

export function apiDetectorStatus(): Promise<StatusResponse> {
  return get<StatusResponse>('/api/process/status');
}

export function apiTestWebhook(): Promise<WebhookResponse> {
  return post<WebhookResponse>('/api/test-webhook');
}

export function apiWakeLockActivate(): Promise<WakeLockResponse> {
  return post<WakeLockResponse>('/api/system/wake-lock');
}

export function apiWakeLockRelease(): Promise<WakeLockResponse> {
  return post<WakeLockResponse>('/api/system/wake-lock/release');
}

export async function apiTranscribe(
  audioBlob: Blob,
  initialPrompt?: string,
): Promise<TranscribeResult> {
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.webm');
  if (initialPrompt) {
    form.append('initial_prompt', initialPrompt);
  }
  try {
    const res = await fetch('/api/transcribe', { method: 'POST', body: form });
    if (!res.ok) throw new Error(`Transcribe failed: ${res.status}`);
    return (await res.json()) as TranscribeResult;
  } catch (err) {
    console.error('api: POST /api/transcribe failed', err);
    throw err;
  }
}
