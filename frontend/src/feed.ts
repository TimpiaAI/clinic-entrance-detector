/**
 * MJPEG fetch-to-canvas renderer.
 *
 * Uses fetch() ReadableStream to receive the multipart MJPEG stream,
 * parses JPEG boundaries via SOI (0xFF 0xD8) and EOI (0xFF 0xD9) markers,
 * draws each frame to a canvas, and immediately revokes the object URL
 * to prevent memory leaks in 24/7 kiosk operation.
 *
 * CRITICAL: Never use <img src="/video_feed"> -- it leaks memory.
 */

let abortController: AbortController | null = null;

export async function startMjpegCanvas(
  url: string,
  canvas: HTMLCanvasElement,
  signal?: AbortSignal,
): Promise<void> {
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    console.error('feed: failed to get canvas 2d context');
    return;
  }

  // Use provided signal or create internal AbortController
  if (!signal) {
    abortController = new AbortController();
    signal = abortController.signal;
  }

  let response: Response;
  try {
    response = await fetch(url, { signal });
  } catch (err) {
    if (signal.aborted) return;
    console.error('feed: fetch failed', err);
    return;
  }

  if (!response.body) {
    console.error('feed: response has no body');
    return;
  }

  const reader = response.body.getReader();
  let buffer = new Uint8Array(0);
  let firstFrame = true;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Append chunk to buffer
      const newBuf = new Uint8Array(buffer.length + value.length);
      newBuf.set(buffer);
      newBuf.set(value, buffer.length);
      buffer = newBuf;

      // Process all complete JPEG frames in the buffer
      while (true) {
        // Find JPEG SOI marker (0xFF 0xD8)
        let startIdx = -1;
        for (let i = 0; i < buffer.length - 1; i++) {
          if (buffer[i] === 0xff && buffer[i + 1] === 0xd8) {
            startIdx = i;
            break;
          }
        }
        if (startIdx === -1) break;

        // Find JPEG EOI marker (0xFF 0xD9) after SOI
        let endIdx = -1;
        for (let i = startIdx + 2; i < buffer.length - 1; i++) {
          if (buffer[i] === 0xff && buffer[i + 1] === 0xd9) {
            endIdx = i + 2;
            break;
          }
        }
        if (endIdx === -1) break;

        // Extract complete JPEG frame
        const jpegBytes = buffer.slice(startIdx, endIdx);
        buffer = buffer.slice(endIdx);

        // Render frame to canvas with explicit memory cleanup
        const blob = new Blob([jpegBytes], { type: 'image/jpeg' });
        const blobUrl = URL.createObjectURL(blob);
        const img = new Image();

        await new Promise<void>((resolve) => {
          img.onload = () => {
            // Set canvas dimensions to match frame on first frame
            if (firstFrame) {
              canvas.width = img.naturalWidth;
              canvas.height = img.naturalHeight;
              firstFrame = false;
            }
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(blobUrl); // CRITICAL: prevents memory leak
            resolve();
          };
          img.onerror = () => {
            URL.revokeObjectURL(blobUrl);
            resolve();
          };
          img.src = blobUrl;
        });
      }
    }
  } catch (err) {
    if (signal.aborted) return;
    console.error('feed: stream read error', err);
  }
}

export function stopMjpegCanvas(): void {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
}
