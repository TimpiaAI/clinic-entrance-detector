"""Main entry point for clinic entrance detection system."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import signal
import sys
import time
from typing import Any

import cv2

from calibration.calibration_tool import run_calibration
from config import Settings, load_settings
from dashboard.web import DashboardServer, DashboardState, create_dashboard_app
from detector.entry_analyzer import EntryAnalyzer, EntryEvent
from detector.person_tracker import PersonTracker, TrackedPerson
from detector.zone_config import CalibrationData, ZoneConfigManager
from training.data_collector import DatasetCollectorConfig, run_collection
from training.trainer import TrainerConfig, run_training
from utils.logger import setup_logger
from utils.snapshot import encode_snapshot_base64
from utils.video_stream import VideoSourceConfig, VideoStream
from webhook.sender import WebhookSender


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clinic Entrance Detection System")
    parser.add_argument("--calibrate", action="store_true", help="Launch interactive calibration tool and exit")
    parser.add_argument(
        "--collect-data",
        action="store_true",
        help="Launch dataset collection mode for model fine-tuning",
    )
    parser.add_argument(
        "--train-model",
        action="store_true",
        help="Fine-tune YOLO model using collected dataset",
    )
    parser.add_argument("--source", choices=["webcam", "rtsp", "file"], help="Video source type")
    parser.add_argument("--url", help="RTSP URL when --source rtsp")
    parser.add_argument("--video", help="Video file path when --source file")
    parser.add_argument("--calibration-file", help="Calibration JSON file path")
    parser.add_argument("--dataset-dir", default="datasets/clinic_person", help="Dataset root directory")
    parser.add_argument("--collect-conf", type=float, default=0.35, help="Proposal confidence in collect mode")
    parser.add_argument("--val-every", type=int, default=5, help="Save every Nth sample to validation split")
    parser.add_argument("--train-epochs", type=int, default=40, help="Training epochs for fine-tuning")
    parser.add_argument("--train-imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--train-batch", type=int, default=16, help="Training batch size")
    parser.add_argument("--train-device", default="cpu", help="Training device (cpu, mps, 0, etc.)")
    parser.add_argument("--train-name", default="clinic_person_finetune", help="Training run name")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable FastAPI dashboard")
    parser.add_argument("--show-window", action="store_true", help="Show local OpenCV preview window")
    parser.add_argument(
        "--debug-boxes",
        action="store_true",
        help="Draw raw YOLO tracking boxes for all detected persons",
    )
    parser.add_argument("--log-level", help="Override log level")
    return parser.parse_args()


def build_source_config(settings: Settings) -> VideoSourceConfig:
    return VideoSourceConfig(
        source_type=settings.VIDEO_SOURCE,
        webcam_index=settings.WEBCAM_INDEX,
        rtsp_url=settings.RTSP_URL,
        video_file=settings.VIDEO_FILE,
        frame_width=settings.FRAME_WIDTH,
        frame_height=settings.FRAME_HEIGHT,
        target_fps=settings.TARGET_FPS,
    )


def apply_runtime_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    if args.source:
        settings.VIDEO_SOURCE = args.source
    if args.url:
        settings.RTSP_URL = args.url
    if args.video:
        settings.VIDEO_FILE = args.video
    if args.calibration_file:
        settings.CALIBRATION_FILE = args.calibration_file
    if args.log_level:
        settings.LOG_LEVEL = args.log_level
    return settings


def _draw_zone_overlay(frame, calibration: CalibrationData, tripwire_triggered: bool, analyzer: Any = None) -> None:
    zone = calibration.entry_zone.normalized()
    trip = calibration.tripwire

    # Draw Zone A (full entry zone) — green tint
    overlay = frame.copy()
    cv2.rectangle(overlay, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 200, 0), -1)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    cv2.rectangle(frame, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 200, 0), 2)
    cv2.putText(frame, "Zone A", (zone.x1 + 5, zone.y1 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1, cv2.LINE_AA)

    # Draw Zone B (inner entrance zone) — yellow/orange tint
    if analyzer is not None and hasattr(analyzer, "zone_b_polygon"):
        zone_b = analyzer.zone_b_polygon
        overlay_b = frame.copy()
        cv2.fillPoly(overlay_b, [zone_b], (0, 180, 255))
        cv2.addWeighted(overlay_b, 0.2, frame, 0.8, 0, frame)
        cv2.polylines(frame, [zone_b], True, (0, 180, 255), 2)
        # Label Zone B
        bx, by = zone_b[0]
        cv2.putText(frame, "Zone B", (int(bx) + 5, int(by) + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 180, 255), 1, cv2.LINE_AA)

    # Tripwire line (legacy, still drawn)
    line_color = (0, 0, 255) if tripwire_triggered else (0, 255, 0)
    cv2.line(frame, (trip.x1, trip.y1), (trip.x2, trip.y2), line_color, 3)


def _style_for_state(state: Any, now_ts: float) -> tuple[tuple[int, int, int], str]:
    if state.direction == "entering":
        if now_ts <= state.flash_until:
            return (0, 255, 0), "ENTERING"
        return (0, 220, 0), "ENTERING"
    if state.direction == "passing":
        return (140, 140, 140), "PASSING"
    if state.direction == "exiting":
        return (80, 80, 255), "EXITING"
    if state.in_entry_zone:
        return (0, 255, 255), "ANALYZING"
    return (255, 120, 0), "TRACKING"


def draw_overlays(
    frame,
    analyzer: EntryAnalyzer,
    calibration: CalibrationData,
    fps: float,
    detections: list[TrackedPerson],
    show_debug_boxes: bool = False,
) -> tuple[Any, list[dict[str, Any]]]:
    now_ts = time.time()
    tripwire_triggered = any(state.direction == "entering" and now_ts <= state.flash_until for state in analyzer.active_states())
    _draw_zone_overlay(frame, calibration, tripwire_triggered, analyzer=analyzer)

    tracked_people: list[dict[str, Any]] = []

    if show_debug_boxes:
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            if x2 <= x1 or y2 <= y1:
                continue
            cv2.rectangle(frame, (x1, y1), (x2, y2), (230, 60, 200), 1)
            cv2.putText(
                frame,
                f"RAW {detection.person_id} {detection.confidence:.2f}",
                (x1, min(frame.shape[0] - 5, y2 + 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (230, 60, 200),
                1,
                cv2.LINE_AA,
            )

    for state in analyzer.active_states():
        x1, y1, x2, y2 = state.last_bbox
        if x2 <= x1 or y2 <= y1:
            continue

        color, label = _style_for_state(state, now_ts)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = f"ID {state.person_id} {label} {state.score_total:.2f}"
        cv2.putText(frame, text, (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

        if show_debug_boxes:
            breakdown = state.score_breakdown or {}
            debug_line = (
                f"TW:{int(state.crossed_tripwire)} "
                f"ZA:{int(state.seen_in_zone_a)} ZB:{int(state.seen_in_zone_b)}({state.consecutive_zone_b_frames}/{state.total_zone_b_frames}) "
                f"B:{breakdown.get('bbox_size', 0.0):.2f} "
                f"Y:{breakdown.get('y_movement', 0.0):.2f} "
                f"D:{breakdown.get('dwell_time', 0.0):.2f} "
                f"V:{breakdown.get('velocity', 0.0):.2f} "
                f"Z:{breakdown.get('zone_cross', 0.0):.2f}"
            )
            cv2.putText(
                frame,
                debug_line,
                (x1, min(frame.shape[0] - 8, y2 + 16)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                color,
                1,
                cv2.LINE_AA,
            )

        if len(state.positions) >= 2:
            sx, sy, _ = state.positions[0]
            ex, ey, _ = state.positions[-1]
            cv2.arrowedLine(frame, (int(sx), int(sy)), (int(ex), int(ey)), color, 2, tipLength=0.3)

        tracked_people.append(
            {
                "person_id": state.person_id,
                "bbox": [x1, y1, x2, y2],
                "direction": state.direction,
                "score": round(state.score_total, 4),
                "confidence": round(state.last_confidence, 4),
            }
        )

    cv2.putText(
        frame,
        f"Entries today: {analyzer.total_entries_today}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"People in frame: {analyzer.current_people()} | Raw det: {len(detections)} | FPS: {fps:.1f}",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    if show_debug_boxes:
        cv2.putText(
            frame,
            (
                f"Dir: {calibration.entry_direction} | "
                f"EntryThr: {analyzer.settings.ENTRY_CONFIDENCE_THRESHOLD:.2f} | "
                "Need ZoneA→ZoneB or TW:1"
            ),
            (20, 102),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (220, 220, 220),
            2,
            cv2.LINE_AA,
        )

    return frame, tracked_people


def build_webhook_payload(
    event: EntryEvent,
    snapshot_b64: str,
    settings: Settings,
    total_entries_today: int,
) -> dict[str, Any]:
    return {
        "event": event.event,
        "timestamp": event.timestamp,
        "confidence": event.confidence,
        "person_id": event.person_id,
        "detection_details": event.detection_details,
        "snapshot": snapshot_b64,
        "metadata": {
            "camera_id": settings.CAMERA_ID,
            "frame_number": event.frame_number,
            "total_entries_today": total_entries_today,
        },
    }


def run() -> int:
    args = parse_args()
    settings = apply_runtime_overrides(load_settings(), args)
    logger = setup_logger(level=settings.LOG_LEVEL)

    source_config = build_source_config(settings)

    if args.collect_data:
        collector_cfg = DatasetCollectorConfig(
            dataset_dir=args.dataset_dir,
            model_name=settings.YOLO_MODEL,
            confidence=max(0.05, min(0.95, float(args.collect_conf))),
            val_every=max(2, int(args.val_every)),
            image_width=settings.FRAME_WIDTH,
            image_height=settings.FRAME_HEIGHT,
            classes=settings.YOLO_CLASSES,
        )
        return run_collection(config=collector_cfg, source_config=source_config, logger=logger)

    if args.train_model:
        trainer_cfg = TrainerConfig(
            dataset_dir=args.dataset_dir,
            base_model=settings.YOLO_MODEL,
            epochs=max(1, int(args.train_epochs)),
            imgsz=max(320, int(args.train_imgsz)),
            batch=max(1, int(args.train_batch)),
            device=args.train_device,
            name=args.train_name,
        )
        try:
            best_path = run_training(config=trainer_cfg, logger=logger)
        except Exception as exc:
            logger.error("Training failed", extra={"extra": {"error": str(exc)}})
            return 1
        logger.info(
            "Use this model for detection",
            extra={
                "extra": {
                    "best_model": str(best_path),
                    "example_command": f"YOLO_MODEL={best_path} python main.py --show-window --debug-boxes",
                }
            },
        )
        return 0

    zone_manager = ZoneConfigManager(settings.CALIBRATION_FILE)
    calibration = zone_manager.load()

    if args.calibrate:
        ok = run_calibration(source_config=source_config, zone_manager=zone_manager, logger=logger)
        return 0 if ok else 1

    stream = VideoStream(source_config)
    if not stream.start():
        logger.error("Failed to start video stream", extra={"extra": {"error": stream.open_error}})
        return 1

    tracker = PersonTracker(
        model_name=settings.YOLO_MODEL,
        confidence=settings.YOLO_CONFIDENCE,
        classes=settings.YOLO_CLASSES,
        tracker_config=settings.TRACKER,
        logger=logger,
        imgsz=settings.YOLO_IMGSZ,
    )

    analyzer = EntryAnalyzer(calibration=calibration, settings=settings, logger=logger)
    webhook_sender = WebhookSender(settings=settings, logger=logger)
    webhook_sender.start()

    dashboard_state = DashboardState()
    dashboard_state.set_calibration(calibration)

    dashboard_server: DashboardServer | None = None
    if not args.no_dashboard:
        app = create_dashboard_app(
            state=dashboard_state,
            zone_manager=zone_manager,
            webhook_sender=webhook_sender,
            analyzer=analyzer,
        )
        dashboard_server = DashboardServer(app, host=settings.DASHBOARD_HOST, port=settings.DASHBOARD_PORT)
        dashboard_server.start()
        logger.info(
            "Dashboard started",
            extra={
                "extra": {
                    "url": f"http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}",
                    "calibration_url": f"http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}/calibrate",
                }
            },
        )

    running = True

    def _stop_handler(signum: int, frame: Any) -> None:
        del signum, frame
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop_handler)
    signal.signal(signal.SIGTERM, _stop_handler)

    if args.show_window:
        cv2.namedWindow("Clinic Entrance Detector", cv2.WINDOW_NORMAL)

    last_perf = time.perf_counter()
    smoothed_fps = 0.0

    try:
        while running:
            frame, ts, frame_number = stream.read()
            if frame is None:
                if stream.eof:
                    logger.info("Video file ended")
                    break
                time.sleep(0.01)
                continue

            if ts <= 0:
                ts = time.time()

            detections = tracker.track(frame=frame, frame_number=frame_number, timestamp=ts)
            events = analyzer.update(detections=detections, now_ts=ts, frame_number=frame_number)

            for event in events:
                if event.event != "person_entered":
                    dashboard_state.push_event(
                        {
                            "event": event.event,
                            "timestamp": event.timestamp,
                            "person_id": event.person_id,
                            "confidence": event.confidence,
                        }
                    )
                    continue

                snapshot = ""
                if settings.WEBHOOK_INCLUDE_SNAPSHOT:
                    snapshot = encode_snapshot_base64(frame, bbox=event.bbox, target_width=640, jpeg_quality=70)

                payload = build_webhook_payload(
                    event=event,
                    snapshot_b64=snapshot,
                    settings=settings,
                    total_entries_today=analyzer.total_entries_today,
                )
                queued = webhook_sender.submit(payload=payload, person_id=event.person_id)
                if not queued:
                    logger.warning(
                        "Webhook skipped due to sender cooldown/state",
                        extra={"extra": {"person_id": event.person_id}},
                    )

                dashboard_state.push_event(
                    {
                        "event": event.event,
                        "timestamp": event.timestamp,
                        "person_id": event.person_id,
                        "confidence": event.confidence,
                        "queued": queued,
                    }
                )

            current_perf = time.perf_counter()
            instant_fps = 1.0 / max(1e-6, current_perf - last_perf)
            smoothed_fps = instant_fps if smoothed_fps == 0 else (smoothed_fps * 0.9 + instant_fps * 0.1)
            last_perf = current_perf

            annotated, tracked_people = draw_overlays(
                frame=frame,
                analyzer=analyzer,
                calibration=analyzer.calibration,
                fps=smoothed_fps,
                detections=detections,
                show_debug_boxes=args.debug_boxes,
            )

            dashboard_state.update_frame(annotated, frame_number=frame_number)
            dashboard_state.update_metrics(
                fps=smoothed_fps,
                current_people=analyzer.current_people(),
                entries_today=analyzer.total_entries_today,
                last_entry_time=analyzer.last_entry_time,
                tracked_people=tracked_people,
                camera_connected=True,
                webhook_status=webhook_sender.status(),
            )
            dashboard_state.set_calibration(analyzer.calibration)

            if args.show_window:
                cv2.imshow("Clinic Entrance Detector", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    running = False

        return 0
    except Exception as exc:
        logger.error("Fatal error in main loop", extra={"extra": {"error": str(exc)}})
        return 1
    finally:
        stream.stop()
        webhook_sender.stop()
        if dashboard_server is not None:
            dashboard_server.stop()
        if args.show_window:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(run())
