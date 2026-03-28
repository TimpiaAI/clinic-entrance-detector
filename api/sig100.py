"""Sig100 signature pad controller via STPadServer WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import threading
from typing import Any

log = logging.getLogger("clinic")

STPAD_URI = "wss://local.signotecwebsocket.de:49494"


def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _send_recv(ws: Any, msg: dict) -> dict:
    """Send a JSON message and wait for response."""
    await ws.send(json.dumps(msg))
    resp = await asyncio.wait_for(ws.recv(), timeout=10)
    return json.loads(resp)


async def activate_signature_pad(
    sign_url: str = "",
    presentation_id: str = "",
    custom_text: str = "Va rugam semnati pentru consimtamant GDPR",
    field_name: str = "GDPR Consent",
    on_signature_captured: Any = None,
) -> dict[str, Any]:
    """Connect to Sig100 via STPadServer and start signature capture.

    Returns dict with signature_image (base64 PNG) and sign_data on success.
    """
    try:
        import websockets
    except ImportError:
        log.error("websockets package not installed - pip install websockets")
        return {"error": "websockets not installed"}

    ssl_ctx = _make_ssl_context()

    try:
        async with websockets.connect(STPAD_URI, ssl=ssl_ctx) as ws:
            log.info("Sig100: connected to STPadServer")

            # 1. Search for pads
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_SEARCH_FOR_PADS",
                "TOKEN_PARAM_PAD_SUBSET": "USB",
            })
            log.info("Sig100: search result: %s", resp.get("TOKEN_PARAM_RETURN_CODE"))

            found_pads = resp.get("TOKEN_PARAM_FOUND_PADS", [])
            if not found_pads:
                log.error("Sig100: no pads found")
                return {"error": "No Sig100 pad found"}

            pad_type = found_pads[0].get("type", "unknown")
            log.info("Sig100: found pad type=%s", pad_type)

            # 2. Open pad
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_OPEN_PAD",
                "TOKEN_PARAM_PAD_INDEX": 0,
            })
            if resp.get("TOKEN_PARAM_RETURN_CODE") != "0":
                log.error("Sig100: open pad failed: %s", resp)
                return {"error": f"Failed to open pad: {resp}"}

            pad_info = resp.get("TOKEN_PARAM_PAD_INFO", {})
            display_w = pad_info.get("displayWidth", 320)
            display_h = pad_info.get("displayHeight", 200)
            log.info("Sig100: pad opened, display=%dx%d", display_w, display_h)

            # 3. Start signature capture
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_START_SIGNATURE",
                "TOKEN_PARAM_FIELD_NAME": field_name,
                "TOKEN_PARAM_CUSTOM_TEXT": custom_text,
                "TOKEN_PARAM_CONFIRMATION_TEXT":
                    "Confirm ca sunt de acord cu prelucrarea datelor personale conform GDPR.",
            })
            if resp.get("TOKEN_PARAM_RETURN_CODE") != "0":
                log.error("Sig100: start signature failed: %s", resp)
                # Close pad
                await _send_recv(ws, {
                    "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                    "TOKEN_CMD": "TOKEN_CMD_CLOSE_PAD",
                    "TOKEN_PARAM_PAD_INDEX": 0,
                })
                return {"error": f"Failed to start signature: {resp}"}

            log.info("Sig100: signature capture started - waiting for patient to sign...")

            # 4. Wait for signature events (confirm/cancel/retry)
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                msg = json.loads(raw)
                cmd = msg.get("TOKEN_CMD") or msg.get("TOKEN_CMD_ORIGIN", "")

                if cmd == "TOKEN_CMD_CONFIRM_SIGNATURE":
                    log.info("Sig100: signature confirmed by patient")
                    break
                elif cmd == "TOKEN_CMD_CANCEL_SIGNATURE":
                    log.info("Sig100: signature cancelled by patient")
                    await _send_recv(ws, {
                        "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                        "TOKEN_CMD": "TOKEN_CMD_CLOSE_PAD",
                        "TOKEN_PARAM_PAD_INDEX": 0,
                    })
                    return {"error": "Signature cancelled by patient"}
                elif cmd == "TOKEN_CMD_RETRY_SIGNATURE":
                    log.info("Sig100: patient wants to retry")
                    continue
                # Ignore signature point events
                elif cmd in ("TOKEN_CMD_NEXT_SIGNATURE_POINT", "TOKEN_CMD_DISCONNECT"):
                    continue

            # 5. Confirm and get signature image
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_CONFIRM_SIGNATURE",
            })

            # 6. Get signature image as PNG
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_GET_SIGNATURE_IMAGE",
                "TOKEN_PARAM_FILE_TYPE": 4,  # PNG
                "TOKEN_PARAM_PEN_WIDTH": 5,
            })
            sig_image = resp.get("TOKEN_PARAM_FILE", "")

            # 7. Get signature data
            resp = await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_GET_SIGNATURE_DATA",
            })
            sign_data = resp.get("TOKEN_PARAM_SIGN_DATA", "")

            # 8. Close pad
            await _send_recv(ws, {
                "TOKEN_TYPE": "TOKEN_TYPE_REQUEST",
                "TOKEN_CMD": "TOKEN_CMD_CLOSE_PAD",
                "TOKEN_PARAM_PAD_INDEX": 0,
            })

            log.info("Sig100: signature captured successfully")

            result = {
                "status": "ok",
                "signature_image": sig_image,
                "sign_data": sign_data,
                "presentation_id": presentation_id,
            }

            if on_signature_captured:
                on_signature_captured(result)

            return result

    except asyncio.TimeoutError:
        log.error("Sig100: timeout waiting for signature (120s)")
        return {"error": "Timeout - patient did not sign within 120 seconds"}
    except Exception as e:
        log.error("Sig100: error: %s", e)
        return {"error": str(e)}


def start_signature_async(
    sign_url: str = "",
    presentation_id: str = "",
    on_done: Any = None,
) -> threading.Thread:
    """Start signature capture in a background thread.

    Returns the thread (already started).
    """
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                activate_signature_pad(
                    sign_url=sign_url,
                    presentation_id=presentation_id,
                    on_signature_captured=on_done,
                )
            )
            if on_done and "error" in result:
                on_done(result)
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True, name="sig100-capture")
    t.start()
    log.info("Sig100: signature capture thread started")
    return t
