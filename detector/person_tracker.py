"""YOLOv8 + ByteTrack person detector and tracker wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class TrackedPerson:
    person_id: int
    bbox: tuple[int, int, int, int]
    confidence: float
    center_bottom: tuple[float, float]
    frame_number: int
    timestamp: float


class PersonTracker:
    """Runs person detection and tracking using Ultralytics YOLOv8 + ByteTrack."""

    def __init__(
        self,
        model_name: str,
        confidence: float,
        classes: list[int],
        tracker_config: str,
        logger: Any,
        imgsz: int = 640,
    ) -> None:
        self.model_name = model_name
        self.confidence = confidence
        self.classes = classes
        self.tracker_config = tracker_config
        self.logger = logger
        self.imgsz = imgsz

        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "ultralytics is required. Install dependencies from requirements.txt"
            ) from exc

        self.model = YOLO(model_name)
        self.logger.info("Loaded YOLO model", extra={"extra": {"model": model_name}})

    def track(self, frame: np.ndarray, frame_number: int, timestamp: float) -> list[TrackedPerson]:
        """Track persons in frame and return normalized tracked outputs."""
        results = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            classes=self.classes,
            tracker=self.tracker_config,
            imgsz=self.imgsz,
            verbose=False,
        )
        if not results:
            return []

        tracked: list[TrackedPerson] = []
        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.xyxy is None:
            return tracked

        ids = boxes.id
        if ids is None:
            return tracked

        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(xyxy), dtype=float)
        track_ids = ids.cpu().numpy()

        for idx in range(len(xyxy)):
            try:
                person_id = int(track_ids[idx])
            except (TypeError, ValueError, OverflowError):
                continue
            x1, y1, x2, y2 = [int(v) for v in xyxy[idx]]
            cx = float((x1 + x2) / 2.0)
            cy_bottom = float(y2)
            tracked.append(
                TrackedPerson(
                    person_id=person_id,
                    bbox=(x1, y1, x2, y2),
                    confidence=float(conf[idx]),
                    center_bottom=(cx, cy_bottom),
                    frame_number=frame_number,
                    timestamp=timestamp,
                )
            )

        return tracked
