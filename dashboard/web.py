"""FastAPI dashboard for live monitoring and calibration."""

from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any

import cv2
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from api.process_manager import detector_status, router as process_router
from api.sleep_guard import router as sleep_router, wake_lock_status
from api.transcribe import router as transcribe_router
from detector.zone_config import CalibrationData, EntryZone, Tripwire, ZoneConfigManager


@dataclass(slots=True)
class DashboardState:
    """Thread-safe data holder shared by detector loop and web server."""

    frame_jpeg: bytes | None = None
    frame_number: int = 0
    fps: float = 0.0
    current_people: int = 0
    entries_today: int = 0
    last_entry_time: str | None = None
    uptime_started: float = field(default_factory=time.time)
    event_log: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    tracked_people: list[dict[str, Any]] = field(default_factory=list)
    camera_connected: bool = False
    webhook_status: dict[str, Any] = field(default_factory=dict)
    calibration: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update_frame(self, frame: Any, frame_number: int) -> None:
        ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return
        with self._lock:
            self.frame_jpeg = jpg.tobytes()
            self.frame_number = frame_number

    def update_metrics(
        self,
        fps: float,
        current_people: int,
        entries_today: int,
        last_entry_time: str | None,
        tracked_people: list[dict[str, Any]],
        camera_connected: bool,
        webhook_status: dict[str, Any],
    ) -> None:
        with self._lock:
            self.fps = fps
            self.current_people = current_people
            self.entries_today = entries_today
            self.last_entry_time = last_entry_time
            self.tracked_people = tracked_people
            self.camera_connected = camera_connected
            self.webhook_status = webhook_status

    def push_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.event_log.appendleft(event)

    def set_calibration(self, calibration: CalibrationData) -> None:
        with self._lock:
            self.calibration = calibration.to_dict()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "frame_number": self.frame_number,
                "fps": self.fps,
                "current_people": self.current_people,
                "entries_today": self.entries_today,
                "last_entry_time": self.last_entry_time,
                "uptime_seconds": round(time.time() - self.uptime_started, 1),
                "event_log": list(self.event_log),
                "tracked_people": self.tracked_people,
                "camera_connected": self.camera_connected,
                "webhook_status": self.webhook_status,
                "calibration": self.calibration,
                "detector_running": detector_status()["running"],
                "wake_lock_active": wake_lock_status()["active"],
            }


class DashboardServer:
    """Threaded Uvicorn runner so dashboard can run with detector loop."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return

        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config)

        def _runner() -> None:
            assert self.server is not None
            self.server.run()

        self.thread = threading.Thread(target=_runner, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=5)


def _templates() -> Jinja2Templates:
    template_dir = Path(__file__).resolve().parent / "templates"
    return Jinja2Templates(directory=str(template_dir))


def _stream_generator(state: DashboardState):
    boundary = b"--frame\r\n"
    while True:
        frame_jpeg = state.frame_jpeg
        if frame_jpeg is None:
            time.sleep(0.1)
            continue
        yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + frame_jpeg + b"\r\n"
        time.sleep(0.066)


def create_dashboard_app(
    state: DashboardState,
    zone_manager: ZoneConfigManager,
    webhook_sender: Any | None = None,
    analyzer: Any | None = None,
    signin_integrator: Any | None = None,
) -> FastAPI:
    templates = _templates()
    app = FastAPI(title="Clinic Entrance Detector Dashboard")

    app.state.dashboard_state = state
    app.state.zone_manager = zone_manager
    app.state.webhook_sender = webhook_sender
    app.state.analyzer = analyzer

    # Only serve old Jinja templates when built frontend is missing (dev fallback)
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
    if not frontend_dist.is_dir():
        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request) -> HTMLResponse:
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "dashboard_port": request.url.port,
                },
            )

    @app.get("/calibrate", response_class=HTMLResponse)
    async def calibrate_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("calibrate.html", {"request": request})

    @app.get("/receptie", response_class=HTMLResponse)
    async def receptie_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("receptie.html", {"request": request})

    @app.get("/signature", response_class=HTMLResponse)
    async def signature_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("signature.html", {"request": request})

    # Serve signotec JS library
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="dashboard_static")

    @app.post("/api/signature-captured")
    async def signature_captured(request: Request) -> JSONResponse:
        """Receive captured signature from Sig100 pad."""
        import logging
        log = logging.getLogger("clinic")
        data = await request.json()
        log.info("Signature captured for presentation %s", data.get("presentation_id"))
        state.push_event({
            "event": "signature_captured",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 1.0,
            "presentation_id": data.get("presentation_id", ""),
        })
        return JSONResponse(content={"status": "ok"})

    @app.post("/api/sign-ready")
    async def sign_ready(request: Request) -> JSONResponse:
        """Kiosk notifies that patient data was submitted and sign URL is ready.

        Opens the Citobiomed GDPR sign page in the default browser.
        That page contains JavaScript that communicates with the Sig100 tablet
        via STPadServer on port 49494.
        """
        import logging
        import subprocess
        log = logging.getLogger("clinic")
        data = await request.json()
        sign_url = data.get("sign_url", "")
        if sign_url:
            state.push_event({
                "event": "sign_ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "person_id": -1,
                "confidence": 1.0,
                "sign_url": sign_url,
            })

            # Open sign URL directly in browser - the Citobiomed page
            # has built-in JavaScript that activates the Sig100 tablet
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", sign_url],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log.info("Sig100: opened sign URL in browser: %s", sign_url)
            except Exception as e:
                log.error("Sig100: failed to open sign URL: %s", e)

        return JSONResponse(content={"status": "ok"})

    @app.post("/api/kiosk-state")
    async def kiosk_state_update(request: Request) -> JSONResponse:
        """Kiosk pushes its current state so receptie can track it live."""
        data = await request.json()
        kiosk_st = data.get("state", "unknown")
        state.push_event({
            "event": "kiosk_state",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 1.0,
            "kiosk_state": kiosk_st,
        })
        return JSONResponse(content={"status": "ok"})

    @app.post("/api/form-abandoned")
    async def form_abandoned() -> JSONResponse:
        """Kiosk notifies that patient form timed out without submission."""
        state.push_event({
            "event": "form_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 1.0,
        })
        return JSONResponse(content={"status": "ok"})

    @app.post("/api/call-patient")
    async def call_patient() -> JSONResponse:
        """Receptionist triggers patient call. Pushed via WebSocket to kiosk."""
        state.push_event({
            "event": "call_patient",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 1.0,
        })
        return JSONResponse(content={"status": "queued"})

    @app.post("/api/call-patient-done")
    async def call_patient_done() -> JSONResponse:
        """Kiosk notifies that CHEAMAPACIENT video finished playing."""
        state.push_event({
            "event": "call_patient_done",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 1.0,
        })
        return JSONResponse(content={"status": "ok"})

    @app.get("/video_feed")
    async def video_feed() -> StreamingResponse:
        return StreamingResponse(
            _stream_generator(state),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(state.snapshot())
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return
        except Exception:
            await websocket.close()

    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(content=state.snapshot())

    @app.get("/api/calibration")
    async def get_calibration() -> JSONResponse:
        calibration = zone_manager.current
        state.set_calibration(calibration)
        return JSONResponse(content=calibration.to_dict())

    @app.post("/api/calibration")
    async def save_calibration(payload: dict[str, Any]) -> JSONResponse:
        try:
            entry_zone = EntryZone(**payload["entry_zone"]) if "entry_zone" in payload else zone_manager.current.entry_zone
            tripwire = Tripwire(**payload["tripwire"]) if "tripwire" in payload else zone_manager.current.tripwire
            direction = payload.get("entry_direction", zone_manager.current.entry_direction)
            frame_width = int(payload.get("frame_width", zone_manager.current.frame_width))
            frame_height = int(payload.get("frame_height", zone_manager.current.frame_height))
            calibration = zone_manager.update(
                entry_zone=entry_zone,
                tripwire=tripwire,
                entry_direction=direction,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            if analyzer is not None:
                analyzer.calibration = calibration
            state.set_calibration(calibration)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid calibration payload: {exc}") from exc
        return JSONResponse(content={"status": "ok", "calibration": calibration.to_dict()})

    @app.post("/api/test-webhook")
    async def test_webhook() -> JSONResponse:
        sender = app.state.webhook_sender
        if sender is None:
            raise HTTPException(status_code=400, detail="Webhook sender not initialized")

        payload = {
            "event": "test_webhook",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": 1.0,
            "person_id": -1,
            "detection_details": {
                "bbox_growth_ratio": 1.0,
                "y_movement_pixels": 0.0,
                "dwell_time_seconds": 0.0,
                "entry_zone_time": 0.0,
                "direction_scores": {
                    "bbox_size": 0.0,
                    "y_movement": 0.0,
                    "dwell_time": 0.0,
                    "tripwire": 0.0,
                },
            },
            "snapshot": "",
            "metadata": {
                "camera_id": "clinic_entrance_01",
                "frame_number": state.frame_number,
                "total_entries_today": state.entries_today,
            },
        }
        queued = sender.submit(payload, person_id=-1)
        if not queued:
            raise HTTPException(status_code=429, detail="Webhook test rejected by cooldown or sender state")
        return JSONResponse(content={"status": "queued", "payload": payload})

    # --- Simulate entry (direct dashboard injection, no external webhook) ---
    @app.post("/api/simulate-entry")
    async def simulate_entry() -> JSONResponse:
        """Inject a fake person_entered event directly into dashboard state."""
        state.push_event({
            "event": "person_entered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "person_id": -1,
            "confidence": 0.99,
            "snapshot": "",
        })
        return JSONResponse(content={"status": "ok"})

    # --- Webhook relay for detector subprocess ---
    @app.post("/trigger")
    async def receive_trigger(request: Request) -> JSONResponse:
        """Receive webhook from detector subprocess, relay to WebSocket clients."""
        payload = await request.json()
        event_type = payload.get("event", "unknown")
        if event_type == "person_entered":
            state.push_event({
                "event": "person_entered",
                "timestamp": payload.get("timestamp", ""),
                "person_id": payload.get("person_id", -1),
                "confidence": payload.get("confidence", 0),
                "snapshot": payload.get("snapshot", ""),
            })
        return JSONResponse(content={"status": "ok"})

    # --- Patient data submission ---
    @app.post("/api/submit-patient")
    async def submit_patient(request: Request) -> JSONResponse:
        """Receive confirmed patient data from frontend workflow.

        Flow:
        1. Refresh today's appointments
        2. Fuzzy match transcribed name against appointments to find patient_id
        3. Determine doctor from CNP gender (1/5→Alexandru, 2/6→Ana)
        4. Create presentation via Functie API
        5. Return sign_url for tablet signature
        """
        import logging
        log = logging.getLogger("clinic")
        data = await request.json()
        name = data.get("name", "")
        cnp = data.get("cnp", "")
        phone = data.get("phone", "")
        email = data.get("email", "noemail@clinic.local")

        log.info(
            "Patient data submitted: name=%s, cnp=%s, phone=%s",
            name, "***" if cnp else None, phone[:4] + "***" if phone else None,
        )

        if signin_integrator is None:
            return JSONResponse(content={"status": "error", "error": "Signin system not initialized"})

        try:
            from api.functie_client import parse_cnp, get_medic_id_from_cnp

            manager = signin_integrator.signin

            # Step 1: Refresh appointments to get latest schedule
            manager.refresh_appointments()
            log.info("Refreshed appointments: %d total", len(manager.all_appointments))

            # Step 2: Fuzzy match transcribed name to find the appointment
            matched_appointment = None
            appointment_id = None
            patient_id_from_appt = None
            if name and manager.all_appointments:
                matches = manager.find_fuzzy_matches(name, threshold=50, top_n=1)
                if matches:
                    matched_appointment = matches[0].appointment
                    appointment_id = matched_appointment.id
                    patient_id_from_appt = matched_appointment.patient_id
                    log.info(
                        "Fuzzy matched: '%s' -> '%s' (score=%.1f, appt_id=%d, patient_id=%d)",
                        name, matched_appointment.full_name, matches[0].score,
                        appointment_id, patient_id_from_appt,
                    )

            # Step 3: Determine doctor from CNP gender, or from explicit gender field
            gender_val = None
            medic_id = 0
            if cnp:
                medic_id = get_medic_id_from_cnp(cnp) or 0
                parsed_cnp = parse_cnp(cnp)
                if parsed_cnp:
                    gender_val = parsed_cnp["gender"]
            if not gender_val:
                # Foreign patient - use explicit gender from form (1=M, 2=F)
                explicit_gender = data.get("gender")
                if explicit_gender in (1, 2, "1", "2", "M", "F", "m", "f"):
                    g = str(explicit_gender).upper()
                    gender_val = 1 if g in ("1", "M") else 2
                    from api.functie_client import MALE_DOCTOR_ID, FEMALE_DOCTOR_ID
                    medic_id = MALE_DOCTOR_ID if gender_val == 1 else FEMALE_DOCTOR_ID
            if not medic_id:
                # Fallback: use the matched appointment's doctor
                if matched_appointment:
                    medic_id = matched_appointment.medic_id
                elif manager.doctors:
                    medic_id = manager.doctors[0].id

            # Use matched appointment names if available (more accurate than transcription)
            if matched_appointment:
                first_name = matched_appointment.first_name
                last_name = matched_appointment.last_name
            else:
                parts = name.strip().split(maxsplit=1) if name else ["", ""]
                first_name = parts[0] if len(parts) > 0 else ""
                last_name = parts[1] if len(parts) > 1 else ""

            # Step 4: Create presentation via Functie API
            response, error = manager.functie.create_presentation(
                medic_id=medic_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone or "0000000000",
                email=email or "noemail@clinic.local",
                appointment_id=appointment_id,
                patient_id=patient_id_from_appt,
                cnp=cnp or None,
                gender=gender_val,
            )
            if error:
                log.error("Presentation creation failed: %s", error)
                return JSONResponse(content={"status": "error", "error": error})

            # Step 5: Build sign URL (uses presentation_id, not patient_id)
            patient_id = response.get("patient_id") if response else patient_id_from_appt
            presentation_id_val = response.get("presentation_id") if response else None
            sign_url = f"https://citobiomed.consultadoctor.ro/gdpr/sign/{presentation_id_val}#" if presentation_id_val else None
            log.info("Presentation created: id=%s, patient=%s, sign_url=%s",
                     response.get("presentation_id") if response else None, patient_id, sign_url)

            # Notify receptie that form is done
            state.push_event({
                "event": "form_completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "person_id": -1,
                "confidence": 1.0,
                "matched_name": matched_appointment.full_name if matched_appointment else name,
            })

            return JSONResponse(content={
                "status": "submitted",
                "presentation_id": response.get("presentation_id") if response else None,
                "patient_id": patient_id,
                "medic_id": medic_id,
                "matched_name": matched_appointment.full_name if matched_appointment else name,
                "appointment_id": appointment_id,
                "sign_url": sign_url,
            })
        except Exception as e:
            log.error("Submit patient error: %s", e)
            # Still notify receptie even on error
            state.push_event({
                "event": "form_completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "person_id": -1,
                "confidence": 1.0,
            })
            return JSONResponse(content={"status": "error", "error": str(e)})

    # Process management endpoints (start/stop/status for detector subprocess)
    app.include_router(process_router)

    # Transcription endpoint (audio -> text + CNP + email extraction)
    app.include_router(transcribe_router)

    # Sleep guard endpoints (wake-lock activation/deactivation)
    app.include_router(sleep_router)

    # Signin API routes (fuzzy matching, appointment confirm, presentation create)
    if signin_integrator is not None:
        from api.signin_api import create_signin_api_routes
        signin_router = create_signin_api_routes(signin_integrator)
        app.include_router(signin_router)

    # --- Video serving with HTTP 206 range support ---
    _video_dir_env = os.getenv("VIDEO_DIR", "")
    video_dir = Path(_video_dir_env) if _video_dir_env else Path(__file__).resolve().parent.parent
    ALLOWED_VIDEOS = {f"video{i}.mp4" for i in range(1, 9)} | {"ADRESADEMAIL.mp4", "CHEAMAPACIENT.mp4", "NUMARTELEFON.mp4"}
    ALLOWED_AUDIO = {"ava_greeting.mp3"}

    @app.get("/api/audio/{filename}")
    async def serve_audio(filename: str) -> Response:
        if filename not in ALLOWED_AUDIO:
            raise HTTPException(status_code=404, detail="Audio not found")

        file_path = video_dir / filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Audio file missing")

        return Response(
            content=file_path.read_bytes(),
            media_type="audio/mpeg",
            headers={
                "Content-Length": str(file_path.stat().st_size),
                "Cache-Control": "public, max-age=86400",
            },
        )

    @app.get("/api/videos/{filename}")
    async def serve_video(filename: str, request: Request) -> Response:
        if filename not in ALLOWED_VIDEOS:
            raise HTTPException(status_code=404, detail="Video not found")

        file_path = video_dir / filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Video file missing")

        file_size = file_path.stat().st_size
        range_header = request.headers.get("range")

        if range_header is None:
            return Response(
                content=file_path.read_bytes(),
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size),
                },
            )

        # Parse Range: bytes=START-END
        range_str = range_header.replace("bytes=", "")
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else min(start + 1024 * 1024, file_size - 1)
        end = min(end, file_size - 1)

        if start > end or start < 0 or start >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        length = end - start + 1
        with open(file_path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        return Response(
            content=data,
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    # --- Deepgram WebSocket proxy (streams mic audio to Deepgram, relays results back) ---
    @app.websocket("/ws/transcribe")
    async def ws_transcribe_proxy(ws: WebSocket):
        """Proxy browser mic audio to Deepgram streaming API, relay results back."""
        import websockets
        import json
        import logging
        log = logging.getLogger("clinic_detector")

        await ws.accept()

        dg_key = os.getenv("DEEPGRAM_API_KEY", "")
        dg_model = os.getenv("DEEPGRAM_MODEL", "nova-3")
        dg_lang = os.getenv("DEEPGRAM_LANGUAGE", "ro")
        dg_url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model={dg_model}&language={dg_lang}"
            f"&punctuate=true&smart_format=true"
            f"&interim_results=true&utterance_end_ms=1500"
            f"&encoding=linear16&sample_rate=16000&channels=1"
        )
        headers = {"Authorization": f"Token {dg_key}"}

        try:
            async with websockets.connect(dg_url, additional_headers=headers) as dg_ws:
                log.info("Deepgram streaming: connected")

                async def forward_audio():
                    """Forward audio chunks from browser to Deepgram."""
                    try:
                        while True:
                            data = await ws.receive_bytes()
                            await dg_ws.send(data)
                    except Exception:
                        # Client disconnected or done - send close to Deepgram
                        await dg_ws.send(json.dumps({"type": "CloseStream"}))

                async def forward_results():
                    """Forward Deepgram results back to browser."""
                    try:
                        async for msg in dg_ws:
                            parsed = json.loads(msg)
                            msg_type = parsed.get("type", "")

                            if msg_type == "Results":
                                channel = parsed.get("channel", {})
                                alts = channel.get("alternatives", [])
                                if alts:
                                    transcript = alts[0].get("transcript", "")
                                    confidence = alts[0].get("confidence", 0)
                                    is_final = parsed.get("is_final", False)
                                    if transcript:
                                        log.info("Deepgram stream: text=%r final=%s conf=%.3f",
                                                 transcript, is_final, confidence)
                                    await ws.send_json({
                                        "type": "transcript",
                                        "text": transcript,
                                        "confidence": confidence,
                                        "is_final": is_final,
                                    })

                            elif msg_type == "UtteranceEnd":
                                log.info("Deepgram stream: utterance_end")
                                await ws.send_json({"type": "utterance_end"})

                    except Exception:
                        pass

                await asyncio.gather(forward_audio(), forward_results())

        except Exception as e:
            log.error("Deepgram streaming error: %s", e)
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    # --- StaticFiles mount for Vite frontend (BACK-01) ---
    # CRITICAL: Mount AFTER all API routes (first-match routing)
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


def run_dashboard_standalone(host: str = "0.0.0.0", port: int = 8080, calibration_file: str = "calibration.json") -> None:
    zone_manager = ZoneConfigManager(calibration_file)
    calibration = zone_manager.load()

    state = DashboardState()
    state.set_calibration(calibration)

    app = create_dashboard_app(state=state, zone_manager=zone_manager)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_dashboard_standalone()
