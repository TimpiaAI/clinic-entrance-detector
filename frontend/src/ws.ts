/**
 * WebSocket client with exponential backoff reconnect.
 *
 * Connects to the /ws endpoint, receives DashboardSnapshot JSON every 0.5s,
 * and automatically reconnects on disconnect with exponential backoff
 * (1s base, 30s max, 2x multiplier, 10% random jitter).
 *
 * Designed for 24/7 kiosk operation -- survives network hiccups,
 * FastAPI restarts, and brief disconnections without operator intervention.
 */

import type { DashboardSnapshot } from './types.ts';

export interface WsOptions {
  url: string;
  onMessage: (data: DashboardSnapshot) => void;
  onStatusChange?: (connected: boolean) => void;
  baseDelay?: number;
  maxDelay?: number;
  multiplier?: number;
}

export function createWsClient(opts: WsOptions): { close: () => void } {
  const { url, onMessage, onStatusChange } = opts;
  const baseDelay = opts.baseDelay ?? 1000;
  const maxDelay = opts.maxDelay ?? 30000;
  const multiplier = opts.multiplier ?? 2;

  let ws: WebSocket | null = null;
  let delay = baseDelay;
  let closed = false;
  let timer: number | null = null;

  function connect(): void {
    if (closed) return;
    ws = new WebSocket(url);

    ws.onopen = () => {
      delay = baseDelay; // Reset delay on successful connect
      onStatusChange?.(true);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data: DashboardSnapshot = JSON.parse(event.data as string);
        onMessage(data);
      } catch (e) {
        console.error('ws: parse error', e);
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      // Close the socket to trigger onclose -> reconnect
      ws?.close();
    };
  }

  function scheduleReconnect(): void {
    if (closed) return;
    const jitter = delay * 0.1 * Math.random();
    timer = window.setTimeout(connect, delay + jitter);
    delay = Math.min(delay * multiplier, maxDelay);
  }

  connect();

  return {
    close(): void {
      closed = true;
      if (timer !== null) clearTimeout(timer);
      ws?.close();
    },
  };
}
