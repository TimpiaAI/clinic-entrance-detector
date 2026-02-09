"""Offline video test: detect entries and save annotated output video."""

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
    parser = argparse.ArgumentParser(description="Run detection against a recorded video")
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument("--output", default="annotated_output.mp4", help="Output annotated video path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    logger = setup_logger("test_video", settings.LOG_LEVEL)

    zone_manager = ZoneConfigManager(settings.CALIBRATION_FILE)
    calibration = zone_manager.load()

    source = VideoSourceConfig(
        source_type="file",
        video_file=args.video,
        frame_width=settings.FRAME_WIDTH,
        frame_height=settings.FRAME_HEIGHT,
        target_fps=settings.TARGET_FPS,
    )
    stream = VideoStream(source)
    if not stream.start():
        print(f"Failed to open video: {stream.open_error}")
        return 1

    tracker = PersonTracker(
        model_name=settings.YOLO_MODEL,
        confidence=settings.YOLO_CONFIDENCE,
        classes=settings.YOLO_CLASSES,
        tracker_config=settings.TRACKER,
        logger=logger,
    )
    analyzer = EntryAnalyzer(calibration=calibration, settings=settings, logger=logger)

    writer = None
    try:
        while True:
            frame, ts, frame_number = stream.read()
            if frame is None:
                if stream.eof:
                    break
                time.sleep(0.01)
                continue

            if writer is None:
                h, w = frame.shape[:2]
                writer = cv2.VideoWriter(
                    args.output,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    max(1, settings.TARGET_FPS),
                    (w, h),
                )

            detections = tracker.track(frame=frame, frame_number=frame_number, timestamp=ts)
            events = analyzer.update(detections=detections, now_ts=ts, frame_number=frame_number)

            for event in events:
                print(f"{event.timestamp} | {event.event} | person_id={event.person_id} | conf={event.confidence:.2f}")

            zone = analyzer.calibration.entry_zone.normalized()
            trip = analyzer.calibration.tripwire
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
                    f"ID {state.person_id} {state.direction}",
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                    cv2.LINE_AA,
                )

            writer.write(frame)
    finally:
        stream.stop()
        if writer is not None:
            writer.release()

    print(f"Saved annotated video to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
