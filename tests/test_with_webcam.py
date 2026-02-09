"""Manual webcam test for entry detection logic without webhook sending."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import load_settings
from detector.entry_analyzer import EntryAnalyzer
from detector.person_tracker import PersonTracker
from detector.zone_config import ZoneConfigManager
from utils.logger import setup_logger
from utils.video_stream import VideoSourceConfig, VideoStream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual webcam test for entry detection")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help="Optional auto-stop timeout. 0 means run until user quits.",
    )
    return parser.parse_args()


def draw_test_overlay(frame, analyzer: EntryAnalyzer) -> None:
    calibration = analyzer.calibration
    zone = calibration.entry_zone.normalized()
    trip = calibration.tripwire

    overlay = frame.copy()
    cv2.rectangle(overlay, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 200, 0), -1)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    cv2.rectangle(frame, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 200, 0), 2)
    cv2.line(frame, (trip.x1, trip.y1), (trip.x2, trip.y2), (0, 255, 255), 2)

    for state in analyzer.active_states():
        x1, y1, x2, y2 = state.last_bbox
        color = (255, 160, 0)
        if state.direction == "entering":
            color = (0, 255, 0)
        elif state.direction == "passing":
            color = (170, 170, 170)
        elif state.direction == "exiting":
            color = (60, 60, 255)
        elif state.in_entry_zone:
            color = (0, 255, 255)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            f"ID {state.person_id} {state.direction} {state.score_total:.2f}",
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )


def main() -> int:
    args = parse_args()
    settings = load_settings()
    logger = setup_logger("test_webcam", settings.LOG_LEVEL)

    zone_manager = ZoneConfigManager(settings.CALIBRATION_FILE)
    calibration = zone_manager.load()

    source = VideoSourceConfig(
        source_type="webcam",
        webcam_index=settings.WEBCAM_INDEX,
        frame_width=settings.FRAME_WIDTH,
        frame_height=settings.FRAME_HEIGHT,
        target_fps=settings.TARGET_FPS,
    )
    stream = VideoStream(source)
    if not stream.start():
        print(f"Failed to open webcam: {stream.open_error}")
        return 1

    tracker = PersonTracker(
        model_name=settings.YOLO_MODEL,
        confidence=settings.YOLO_CONFIDENCE,
        classes=settings.YOLO_CLASSES,
        tracker_config=settings.TRACKER,
        logger=logger,
    )
    analyzer = EntryAnalyzer(calibration=calibration, settings=settings, logger=logger)

    cv2.namedWindow("Webcam Test", cv2.WINDOW_NORMAL)

    print("Webcam test started. Walk toward camera for ENTERING, sideways for PASSING. Press q to quit.")

    try:
        started_at = time.time()
        while True:
            if args.max_seconds > 0 and time.time() - started_at >= args.max_seconds:
                break
            frame, ts, frame_number = stream.read()
            if frame is None:
                time.sleep(0.01)
                continue

            detections = tracker.track(frame=frame, frame_number=frame_number, timestamp=ts)
            events = analyzer.update(detections=detections, now_ts=ts, frame_number=frame_number)

            for event in events:
                if event.event == "person_entered":
                    print(f"ENTERING DETECTED | person_id={event.person_id} conf={event.confidence:.2f}")
                elif event.event == "person_exited":
                    print(f"EXITING DETECTED  | person_id={event.person_id} conf={event.confidence:.2f}")

            draw_test_overlay(frame, analyzer)
            cv2.imshow("Webcam Test", frame)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
    finally:
        stream.stop()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
