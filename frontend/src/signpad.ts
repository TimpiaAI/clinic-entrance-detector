/**
 * Sig100 signature pad integration via signotec STPadServer WebSocket.
 *
 * Requires STPadServerLib-3.5.0.js loaded as a global <script> before use.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const STPadServerLibCommons: any;
declare const STPadServerLibDefault: any;

// ---------------------------------------------------------------------------
//  Config
// ---------------------------------------------------------------------------

const WS_URI = 'wss://local.signotecwebsocket.de:49494';
const PAD_INDEX = 0;
const MIN_SIGN_SECONDS = 0.2;

// ---------------------------------------------------------------------------
//  Types
// ---------------------------------------------------------------------------

export type PadStatus = 'idle' | 'connecting' | 'ready' | 'signing' | 'captured' | 'error';

export interface SignatureResult {
  imageBase64: string;
  signData: string;
}

// ---------------------------------------------------------------------------
//  State
// ---------------------------------------------------------------------------

let padOpened = false;
let scaleX = 1;
let scaleY = 1;
let sampleRate = 500;
let prevX = -1;
let prevY = -1;
let canvas: HTMLCanvasElement | null = null;
let result: SignatureResult | null = null;

let onStatus: ((s: PadStatus, msg?: string) => void) | null = null;
let onConfirm: ((r: SignatureResult) => void) | null = null;
let onCancel: (() => void) | null = null;

// ---------------------------------------------------------------------------
//  Public API — callbacks & getters
// ---------------------------------------------------------------------------

export function setCanvas(el: HTMLCanvasElement | null): void {
  canvas = el;
}

export function onStatusChange(cb: (s: PadStatus, msg?: string) => void): void {
  onStatus = cb;
}

export function onSignatureConfirmed(cb: (r: SignatureResult) => void): void {
  onConfirm = cb;
}

export function onSignatureCancelled(cb: () => void): void {
  onCancel = cb;
}

export function getResult(): SignatureResult | null {
  return result;
}

export function clearResult(): void {
  result = null;
}

export function isAvailable(): boolean {
  return typeof STPadServerLibCommons !== 'undefined' &&
         typeof STPadServerLibDefault !== 'undefined';
}

// ---------------------------------------------------------------------------
//  Internal helpers
// ---------------------------------------------------------------------------

function emit(s: PadStatus, msg?: string): void {
  if (onStatus) onStatus(s, msg);
}

function clearCanvas(): void {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
  prevX = -1;
  prevY = -1;
}

function drawPoint(x: number, y: number, p: number): void {
  if (!canvas) return;
  const cx = x * scaleX;
  const cy = y * scaleY;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  if (p > 0) {
    ctx.strokeStyle = '#1e3a5f';
    ctx.lineWidth = Math.max(1, Math.min(3, p / 300));
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (prevX >= 0 && prevY >= 0) {
      ctx.beginPath();
      ctx.moveTo(prevX, prevY);
      ctx.lineTo(cx, cy);
      ctx.stroke();
    }
    prevX = cx;
    prevY = cy;
  } else {
    prevX = -1;
    prevY = -1;
  }
}

// ---------------------------------------------------------------------------
//  Confirm flow — called when patient presses ✓ on pad
// ---------------------------------------------------------------------------

async function doConfirm(): Promise<void> {
  try {
    const sig = await STPadServerLibDefault.confirmSignature();

    // Reject signatures shorter than MIN_SIGN_SECONDS
    if ((sig.countedPoints / sampleRate) <= MIN_SIGN_SECONDS) {
      await STPadServerLibDefault.retrySignature();
      clearCanvas();
      emit('signing');
      return;
    }

    // Get PNG image
    const ip = new STPadServerLibDefault.Params.getSignatureImage();
    ip.setFileType(STPadServerLibDefault.FileType.PNG);
    ip.setPenWidth(5);
    const img = await STPadServerLibDefault.getSignatureImage(ip);

    // Get biometric data
    const dp = new STPadServerLibDefault.Params.getSignatureData();
    const sd = await STPadServerLibDefault.getSignatureData(dp);

    await closePad();

    result = { imageBase64: img.file, signData: sd.signData || '' };
    emit('captured');
    if (onConfirm) onConfirm(result);
  } catch (err: any) {
    console.error('signpad: confirm error', err);
    emit('error', err.message || String(err));
  }
}

// ---------------------------------------------------------------------------
//  Pad lifecycle
// ---------------------------------------------------------------------------

export async function closePad(): Promise<void> {
  if (!padOpened) return;
  try {
    const p = new STPadServerLibDefault.Params.closePad(PAD_INDEX);
    await STPadServerLibDefault.closePad(p);
  } catch (_) { /* ignore */ }
  padOpened = false;
}

export function disconnect(): void {
  closePad();
  try { STPadServerLibCommons.destroyConnection(); } catch (_) { /* ignore */ }
  emit('idle');
}

export async function activate(): Promise<boolean> {
  result = null;
  prevX = -1;
  prevY = -1;

  if (!isAvailable()) {
    emit('error', 'STPadServer library not loaded');
    return false;
  }

  // Register signotec callbacks
  STPadServerLibCommons.handleNextSignaturePoint = drawPoint;

  STPadServerLibDefault.handleRetrySignature = () => {
    clearCanvas();
    emit('signing');
  };

  STPadServerLibDefault.handleConfirmSignature = () => {
    doConfirm();
  };

  STPadServerLibDefault.handleCancelSignature = () => {
    closePad();
    emit('error', 'Cancelled');
    if (onCancel) onCancel();
  };

  STPadServerLibCommons.handleDisconnect = () => {
    padOpened = false;
    emit('error', 'Disconnected');
  };

  emit('connecting');

  try {
    // Connect to local STPadServer via WebSocket
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      STPadServerLibCommons.createConnection(
        WS_URI,
        () => { settled = true; resolve(); },
        () => { if (!settled) { settled = true; reject(new Error('Connection closed')); } },
        () => { if (!settled) { settled = true; reject(new Error('WebSocket error')); } },
      );
    });

    // Search for USB signature pads
    const sp = new STPadServerLibDefault.Params.searchForPads();
    sp.setPadSubset('USB');
    const found = await STPadServerLibDefault.searchForPads(sp);

    if (found.foundPads.length === 0) {
      emit('error', 'No pad found');
      return false;
    }

    // Open the first pad
    const op = new STPadServerLibDefault.Params.openPad(PAD_INDEX);
    const info = await STPadServerLibDefault.openPad(op);
    padOpened = true;

    const dw = info.padInfo.displayWidth;
    const dh = info.padInfo.displayHeight;
    scaleX = dw / info.padInfo.xResolution;
    scaleY = dh / info.padInfo.yResolution;
    sampleRate = info.padInfo.samplingRate;

    if (canvas) {
      canvas.width = dw;
      canvas.height = dh;
    }

    // Start signature capture — display "Acord GDPR" on pad screen
    const sigP = new STPadServerLibDefault.Params.startSignature();
    sigP.setFieldName('Acord GDPR');
    sigP.setCustomText('Semnati aici');
    await STPadServerLibDefault.startSignature(sigP);

    emit('signing');
    return true;
  } catch (err: any) {
    console.error('signpad: activate error', err);
    emit('error', err.message || String(err));
    return false;
  }
}
