"""FastAPI dashboard for live monitoring and calibration."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any

import cv2
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from api.process_manager import router as process_router
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
        snap = state.snapshot()
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
) -> FastAPI:
    templates = _templates()
    app = FastAPI(title="Clinic Entrance Detector Dashboard")

    app.state.dashboard_state = state
    app.state.zone_manager = zone_manager
    app.state.webhook_sender = webhook_sender
    app.state.analyzer = analyzer

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

    # Process management endpoints (start/stop/status for detector subprocess)
    app.include_router(process_router)

    # Transcription endpoint (audio -> text + CNP + email extraction)
    app.include_router(transcribe_router)

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
