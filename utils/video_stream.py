"""Video stream abstraction for webcam, RTSP, and file sources."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np


SourceType = Literal["webcam", "rtsp", "file"]


@dataclass(slots=True)
class VideoSourceConfig:
    source_type: SourceType
    webcam_index: int = 0
    rtsp_url: str = ""
    video_file: str = ""
    frame_width: int = 1280
    frame_height: int = 720
    target_fps: int = 15


class VideoStream:
    """Threaded frame reader for stable frame acquisition."""

    def __init__(self, config: VideoSourceConfig) -> None:
        self.config = config
        self.capture: cv2.VideoCapture | None = None
        self.frame_lock = threading.Lock()
        self.latest_frame: np.ndarray | None = None
        self.latest_ts: float = 0.0
        self.running = False
        self.thread: threading.Thread | None = None
        self.frame_counter = 0
        self._open_error: str | None = None
        self._eof = False

    @property
    def eof(self) -> bool:
        return self._eof

    @property
    def open_error(self) -> str | None:
        return self._open_error

    def _resolve_source(self) -> int | str:
        if self.config.source_type == "webcam":
            return self.config.webcam_index
        if self.config.source_type == "rtsp":
            return self.config.rtsp_url
        return self.config.video_file

    def start(self) -> bool:
        source = self._resolve_source()
        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            self._open_error = f"Failed to open video source: {source}"
            return False

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        self.capture.set(cv2.CAP_PROP_FPS, self.config.target_fps)

        self.running = True
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()
        return True

    def _reader_loop(self) -> None:
        sleep_time = 1.0 / max(1, self.config.target_fps)
        while self.running and self.capture is not None:
            ok, frame = self.capture.read()
            if not ok:
                if self.config.source_type == "file":
                    self._eof = True
                    self.running = False
                    break
                time.sleep(0.05)
                continue

            ts = time.time()
            with self.frame_lock:
                self.latest_frame = frame
                self.latest_ts = ts
                self.frame_counter += 1
            time.sleep(sleep_time)

    def read(self) -> tuple[np.ndarray | None, float, int]:
        with self.frame_lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
            ts = self.latest_ts
            count = self.frame_counter
        return frame, ts, count

    def stop(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.capture is not None:
            self.capture.release()
            self.capture = None
