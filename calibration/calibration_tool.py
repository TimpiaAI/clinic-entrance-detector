"""Interactive OpenCV calibration tool for entry zone and tripwire setup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import cv2

from detector.zone_config import CalibrationData, EntryZone, Point, Tripwire, ZoneConfigManager
from utils.video_stream import VideoSourceConfig, VideoStream


DIRECTIONS = ["top_to_bottom", "bottom_to_top", "left_to_right", "right_to_left"]


@dataclass(slots=True)
class _MouseState:
    mode: str = "zone"
    dragging: bool = False
    zone_start: tuple[int, int] | None = None
    zone_end: tuple[int, int] | None = None
    tripwire_points: list[Point] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.tripwire_points is None:
            self.tripwire_points = []


class CalibrationTool:
    """Calibration utility that writes camera geometry to calibration.json."""

    def __init__(self, source_config: VideoSourceConfig, zone_manager: ZoneConfigManager, logger: Any) -> None:
        self.source_config = source_config
        self.zone_manager = zone_manager
        self.logger = logger
        self.stream = VideoStream(source_config)
        self.calibration = self.zone_manager.load()
        self.mouse = _MouseState()
        self.window_name = "Clinic Calibration"

    def _draw_overlay(self, frame):
        zone = self.calibration.entry_zone.normalized()
        trip = self.calibration.tripwire

        overlay = frame.copy()
        cv2.rectangle(overlay, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 180, 0), 2)
        cv2.line(overlay, (trip.x1, trip.y1), (trip.x2, trip.y2), (0, 255, 255), 2)

        alpha = 0.2
        cv2.rectangle(overlay, (zone.x1, zone.y1), (zone.x2, zone.y2), (0, 200, 0), -1)
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        info_lines = [
            f"Mode: {self.mouse.mode}",
            f"Direction: {self.calibration.entry_direction}",
            "Keys: [z]=zone [t]=tripwire [d]=direction [s]=save [r]=reset [q]=quit",
        ]
        for idx, line in enumerate(info_lines):
            cv2.putText(
                frame,
                line,
                (20, 30 + idx * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return frame

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        del flags, param

        if self.mouse.mode == "zone":
            if event == cv2.EVENT_LBUTTONDOWN:
                self.mouse.dragging = True
                self.mouse.zone_start = (x, y)
                self.mouse.zone_end = (x, y)
            elif event == cv2.EVENT_MOUSEMOVE and self.mouse.dragging:
                self.mouse.zone_end = (x, y)
            elif event == cv2.EVENT_LBUTTONUP and self.mouse.dragging:
                self.mouse.dragging = False
                self.mouse.zone_end = (x, y)
                if self.mouse.zone_start and self.mouse.zone_end:
                    x1, y1 = self.mouse.zone_start
                    x2, y2 = self.mouse.zone_end
                    self.calibration.entry_zone = EntryZone(x1, y1, x2, y2).normalized()

        elif self.mouse.mode == "tripwire" and event == cv2.EVENT_LBUTTONDOWN:
            self.mouse.tripwire_points.append(Point(x, y))
            if len(self.mouse.tripwire_points) == 2:
                p1, p2 = self.mouse.tripwire_points
                self.calibration.tripwire = Tripwire(p1.x, p1.y, p2.x, p2.y)
                self.mouse.tripwire_points.clear()

    def _cycle_direction(self) -> None:
        current = self.calibration.entry_direction
        idx = DIRECTIONS.index(current)
        self.calibration.entry_direction = DIRECTIONS[(idx + 1) % len(DIRECTIONS)]

    def _reset(self, frame_width: int, frame_height: int) -> None:
        self.calibration = CalibrationData.default(width=frame_width, height=frame_height)

    def _save(self) -> None:
        self.calibration.calibrated_at = datetime.now(timezone.utc).isoformat()
        self.zone_manager.save(self.calibration)
        self.logger.info("Calibration saved", extra={"extra": self.calibration.to_dict()})

    def run(self) -> bool:
        if not self.stream.start():
            self.logger.error("Calibration stream failed to start", extra={"extra": {"error": self.stream.open_error}})
            return False

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self._on_mouse)

        try:
            while True:
                frame, _, _ = self.stream.read()
                if frame is None:
                    if self.stream.eof:
                        break
                    cv2.waitKey(1)
                    continue

                h, w = frame.shape[:2]
                self.calibration.frame_width = w
                self.calibration.frame_height = h

                if self.mouse.dragging and self.mouse.zone_start and self.mouse.zone_end:
                    sx, sy = self.mouse.zone_start
                    ex, ey = self.mouse.zone_end
                    cv2.rectangle(frame, (sx, sy), (ex, ey), (255, 100, 0), 2)

                frame = self._draw_overlay(frame)
                cv2.imshow(self.window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("z"):
                    self.mouse.mode = "zone"
                elif key == ord("t"):
                    self.mouse.mode = "tripwire"
                elif key == ord("d"):
                    self._cycle_direction()
                elif key == ord("s"):
                    self._save()
                elif key == ord("r"):
                    self._reset(frame_width=w, frame_height=h)
        finally:
            self.stream.stop()
            cv2.destroyAllWindows()

        return True


def run_calibration(source_config: VideoSourceConfig, zone_manager: ZoneConfigManager, logger: Any) -> bool:
    tool = CalibrationTool(source_config=source_config, zone_manager=zone_manager, logger=logger)
    return tool.run()
