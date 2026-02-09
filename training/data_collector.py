"""Interactive dataset collection tool for person detection fine-tuning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import cv2
import numpy as np

from utils.video_stream import VideoSourceConfig, VideoStream


@dataclass(slots=True)
class DatasetCollectorConfig:
    dataset_dir: str = "datasets/clinic_person"
    model_name: str = "yolov8n.pt"
    confidence: float = 0.35
    val_every: int = 5
    image_width: int = 1280
    image_height: int = 720
    classes: list[int] | None = None


def _clamp_bbox(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(x1)))
    y1 = max(0, min(height - 1, int(y1)))
    x2 = max(0, min(width - 1, int(x2)))
    y2 = max(0, min(height - 1, int(y2)))
    if x2 <= x1:
        x2 = min(width - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(height - 1, y1 + 1)
    return x1, y1, x2, y2


def _bbox_to_yolo_line(box: tuple[int, int, int, int], width: int, height: int) -> str:
    x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


class DatasetCollector:
    """Collects labeled frames with manual and assisted annotations."""

    def __init__(
        self,
        collector_config: DatasetCollectorConfig,
        source_config: VideoSourceConfig,
        logger: Any,
    ) -> None:
        self.config = collector_config
        self.source_config = source_config
        self.logger = logger

        self.dataset_path = Path(self.config.dataset_dir)
        self.images_train = self.dataset_path / "images" / "train"
        self.images_val = self.dataset_path / "images" / "val"
        self.labels_train = self.dataset_path / "labels" / "train"
        self.labels_val = self.dataset_path / "labels" / "val"

        self.stream = VideoStream(source_config)

        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("ultralytics is required for dataset collection") from exc

        self.model = YOLO(self.config.model_name)

        self.window = "Training Data Collector"
        self.paused = False
        self.use_proposals_if_empty = True
        self.current_frame: np.ndarray | None = None
        self.current_proposals: list[tuple[int, int, int, int]] = []
        self.current_annotations: list[tuple[int, int, int, int]] = []

        self.dragging = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None

        self.saved_total = 0
        self.saved_train = 0
        self.saved_val = 0

    def _ensure_dirs(self) -> None:
        for path in [self.images_train, self.images_val, self.labels_train, self.labels_val]:
            path.mkdir(parents=True, exist_ok=True)

    def _next_sample_name(self) -> str:
        ts = int(time.time() * 1000)
        return f"sample_{ts}_{self.saved_total:05d}"

    def _assign_split(self) -> str:
        val_every = max(2, int(self.config.val_every))
        return "val" if (self.saved_total + 1) % val_every == 0 else "train"

    def _detect_proposals(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        results = self.model.predict(
            frame,
            conf=self.config.confidence,
            classes=self.config.classes if self.config.classes is not None else [0],
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.xyxy is None:
            return []

        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        h, w = frame.shape[:2]
        proposals: list[tuple[int, int, int, int]] = []
        for row in xyxy:
            x1, y1, x2, y2 = [int(v) for v in row]
            proposals.append(_clamp_bbox((x1, y1, x2, y2), w, h))
        return proposals

    def _save_sample(self) -> None:
        if self.current_frame is None:
            return

        frame = self.current_frame.copy()
        h, w = frame.shape[:2]

        labels = list(self.current_annotations)
        if not labels and self.use_proposals_if_empty:
            labels = list(self.current_proposals)

        if not labels:
            self.logger.info("No labels to save. Draw boxes or press P to copy proposals first.")
            return

        labels = [_clamp_bbox(b, w, h) for b in labels]
        split = self._assign_split()
        sample_name = self._next_sample_name()

        if split == "train":
            image_path = self.images_train / f"{sample_name}.jpg"
            label_path = self.labels_train / f"{sample_name}.txt"
            self.saved_train += 1
        else:
            image_path = self.images_val / f"{sample_name}.jpg"
            label_path = self.labels_val / f"{sample_name}.txt"
            self.saved_val += 1

        ok = cv2.imwrite(str(image_path), frame)
        if not ok:
            self.logger.error("Failed to save image", extra={"extra": {"path": str(image_path)}})
            return

        with label_path.open("w", encoding="utf-8") as fp:
            for box in labels:
                fp.write(_bbox_to_yolo_line(box, w, h) + "\n")

        self.saved_total += 1
        self.logger.info(
            "Saved dataset sample",
            extra={
                "extra": {
                    "split": split,
                    "image": str(image_path),
                    "labels": len(labels),
                    "total": self.saved_total,
                }
            },
        )

    def _remove_nearest_annotation(self, x: int, y: int) -> None:
        if not self.current_annotations:
            return
        distances = []
        for idx, (x1, y1, x2, y2) in enumerate(self.current_annotations):
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            d2 = (cx - x) ** 2 + (cy - y) ** 2
            distances.append((d2, idx))
        distances.sort(key=lambda t: t[0])
        d2, idx = distances[0]
        if d2 < 18000:  # around 134px radius
            self.current_annotations.pop(idx)

    def _mouse_cb(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        del flags, param
        if self.current_frame is None:
            return

        h, w = self.current_frame.shape[:2]

        if event == cv2.EVENT_LBUTTONDOWN:
            self.dragging = True
            self.drag_start = (x, y)
            self.drag_end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            self.drag_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self.dragging:
            self.dragging = False
            self.drag_end = (x, y)
            if self.drag_start is not None and self.drag_end is not None:
                sx, sy = self.drag_start
                ex, ey = self.drag_end
                box = _clamp_bbox((min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey)), w, h)
                # Ignore tiny accidental boxes
                if (box[2] - box[0]) > 8 and (box[3] - box[1]) > 12:
                    self.current_annotations.append(box)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._remove_nearest_annotation(x, y)

    def _draw_ui(self, frame: np.ndarray) -> np.ndarray:
        canvas = frame.copy()

        for x1, y1, x2, y2 in self.current_proposals:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (220, 70, 220), 1)
            cv2.putText(canvas, "proposal", (x1, max(15, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 70, 220), 1, cv2.LINE_AA)

        for x1, y1, x2, y2 in self.current_annotations:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(canvas, "label", (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 0), 1, cv2.LINE_AA)

        if self.dragging and self.drag_start is not None and self.drag_end is not None:
            sx, sy = self.drag_start
            ex, ey = self.drag_end
            cv2.rectangle(canvas, (sx, sy), (ex, ey), (0, 150, 255), 2)

        lines = [
            f"Paused: {'YES' if self.paused else 'NO'} | Saved total/train/val: {self.saved_total}/{self.saved_train}/{self.saved_val}",
            f"Annotations: {len(self.current_annotations)} | Proposals: {len(self.current_proposals)} | Auto-proposal-on-save: {'ON' if self.use_proposals_if_empty else 'OFF'}",
            "Keys: [space]=pause [p]=copy proposals [c]=clear labels [s]=save [a]=toggle auto [q]=quit",
            "Mouse: Left drag = add label box | Right click = remove nearest box",
        ]

        y = 26
        for line in lines:
            cv2.putText(canvas, line, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)
            y += 24

        return canvas

    def run(self) -> int:
        self._ensure_dirs()

        if not self.stream.start():
            self.logger.error("Failed to start source stream", extra={"extra": {"error": self.stream.open_error}})
            return 1

        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window, self._mouse_cb)

        self.logger.info(
            "Dataset collector started",
            extra={"extra": {"dataset_dir": str(self.dataset_path), "model": self.config.model_name}},
        )

        try:
            while True:
                if not self.paused or self.current_frame is None:
                    frame, _, _ = self.stream.read()
                    if frame is None:
                        if self.stream.eof:
                            break
                        key = cv2.waitKey(1) & 0xFF
                        if key in (ord("q"), 27):
                            break
                        continue
                    self.current_frame = frame
                    self.current_proposals = self._detect_proposals(frame)
                    self.current_annotations = []

                assert self.current_frame is not None
                ui = self._draw_ui(self.current_frame)
                cv2.imshow(self.window, ui)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord(" "):
                    self.paused = not self.paused
                elif key == ord("p"):
                    self.current_annotations = list(self.current_proposals)
                elif key == ord("c"):
                    self.current_annotations = []
                elif key == ord("a"):
                    self.use_proposals_if_empty = not self.use_proposals_if_empty
                elif key == ord("s"):
                    self._save_sample()

            return 0
        finally:
            self.stream.stop()
            cv2.destroyAllWindows()


def run_collection(config: DatasetCollectorConfig, source_config: VideoSourceConfig, logger: Any) -> int:
    collector = DatasetCollector(collector_config=config, source_config=source_config, logger=logger)
    return collector.run()
