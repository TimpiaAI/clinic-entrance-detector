"""Application configuration for clinic entrance detection system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


SourceType = Literal["webcam", "rtsp", "file"]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None else raw


@dataclass(slots=True)
class Settings:
    # === Video Source ===
    VIDEO_SOURCE: SourceType = "webcam"
    WEBCAM_INDEX: int = 0
    RTSP_URL: str = ""
    VIDEO_FILE: str = ""
    FRAME_WIDTH: int = 1280
    FRAME_HEIGHT: int = 720
    TARGET_FPS: int = 15

    # === Detection ===
    YOLO_MODEL: str = "yolo11n.pt"
    YOLO_CONFIDENCE: float = 0.5
    YOLO_CLASSES: list[int] = field(default_factory=lambda: [0])
    TRACKER: str = "botsort_tuned.yaml"
    YOLO_IMGSZ: int = 640

    # === Entry Detection Thresholds ===
    BBOX_GROWTH_RATIO: float = 1.3
    Y_MOVEMENT_THRESHOLD: int = 50
    DWELL_TIME_MIN: float = 1.5
    DWELL_TIME_MAX: float = 15.0
    ENTRY_CONFIDENCE_THRESHOLD: float = 0.6
    TRAJECTORY_HISTORY_SECONDS: int = 5

    # === Webhook ===
    WEBHOOK_URL: str = "https://example.com/webhook"
    WEBHOOK_TIMEOUT: int = 5
    WEBHOOK_RETRY_COUNT: int = 3
    WEBHOOK_RETRY_DELAY: int = 2
    WEBHOOK_COOLDOWN_PERSON: int = 30
    WEBHOOK_COOLDOWN_GLOBAL: int = 3
    WEBHOOK_INCLUDE_SNAPSHOT: bool = True
    WEBHOOK_SECRET: str = ""

    # === Zone Tuning ===
    ZONE_B_SPLIT_RATIO: float = 0.35
    MIN_ZONE_B_FRAMES: int = 5
    MIN_BBOX_AREA: int = 2000

    # === Cleanup ===
    PERSON_TIMEOUT: int = 5
    MAX_TRACKED_PERSONS: int = 50
    ENTRY_LOG_SIZE: int = 100

    # === Dashboard ===
    DASHBOARD_PORT: int = 8080
    DASHBOARD_HOST: str = "0.0.0.0"

    # === Calibration ===
    CALIBRATION_FILE: str = "calibration.json"

    # === Metadata ===
    CAMERA_ID: str = "clinic_entrance_01"
    LOG_LEVEL: str = "INFO"


def load_settings(env_path: str | Path | None = None) -> Settings:
    """Load settings from defaults, .env, and process env variables."""
    if env_path is None:
        load_dotenv(override=False)
    else:
        load_dotenv(dotenv_path=env_path, override=False)

    classes_raw = _env_str("YOLO_CLASSES", "0")
    classes = []
    for value in classes_raw.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            classes.append(int(value))
        except ValueError:
            continue
    if not classes:
        classes = [0]

    source = _env_str("VIDEO_SOURCE", "webcam").strip().lower()
    if source not in {"webcam", "rtsp", "file"}:
        source = "webcam"

    return Settings(
        VIDEO_SOURCE=source,  # type: ignore[arg-type]
        WEBCAM_INDEX=_env_int("WEBCAM_INDEX", 0),
        RTSP_URL=_env_str("RTSP_URL", ""),
        VIDEO_FILE=_env_str("VIDEO_FILE", ""),
        FRAME_WIDTH=_env_int("FRAME_WIDTH", 1280),
        FRAME_HEIGHT=_env_int("FRAME_HEIGHT", 720),
        TARGET_FPS=_env_int("TARGET_FPS", 15),
        YOLO_MODEL=_env_str("YOLO_MODEL", "yolo11n.pt"),
        YOLO_CONFIDENCE=_env_float("YOLO_CONFIDENCE", 0.5),
        YOLO_CLASSES=classes,
        TRACKER=_env_str("TRACKER", "botsort_tuned.yaml"),
        YOLO_IMGSZ=_env_int("YOLO_IMGSZ", 640),
        BBOX_GROWTH_RATIO=_env_float("BBOX_GROWTH_RATIO", 1.3),
        Y_MOVEMENT_THRESHOLD=_env_int("Y_MOVEMENT_THRESHOLD", 50),
        DWELL_TIME_MIN=_env_float("DWELL_TIME_MIN", 1.5),
        DWELL_TIME_MAX=_env_float("DWELL_TIME_MAX", 15.0),
        ENTRY_CONFIDENCE_THRESHOLD=_env_float("ENTRY_CONFIDENCE_THRESHOLD", 0.6),
        TRAJECTORY_HISTORY_SECONDS=_env_int("TRAJECTORY_HISTORY_SECONDS", 5),
        ZONE_B_SPLIT_RATIO=_env_float("ZONE_B_SPLIT_RATIO", 0.35),
        MIN_ZONE_B_FRAMES=_env_int("MIN_ZONE_B_FRAMES", 5),
        MIN_BBOX_AREA=_env_int("MIN_BBOX_AREA", 2000),
        WEBHOOK_URL=_env_str("WEBHOOK_URL", "https://example.com/webhook"),
        WEBHOOK_TIMEOUT=_env_int("WEBHOOK_TIMEOUT", 5),
        WEBHOOK_RETRY_COUNT=_env_int("WEBHOOK_RETRY_COUNT", 3),
        WEBHOOK_RETRY_DELAY=_env_int("WEBHOOK_RETRY_DELAY", 2),
        WEBHOOK_COOLDOWN_PERSON=_env_int("WEBHOOK_COOLDOWN_PERSON", 30),
        WEBHOOK_COOLDOWN_GLOBAL=_env_int("WEBHOOK_COOLDOWN_GLOBAL", 3),
        WEBHOOK_INCLUDE_SNAPSHOT=_env_bool("WEBHOOK_INCLUDE_SNAPSHOT", True),
        WEBHOOK_SECRET=_env_str("WEBHOOK_SECRET", ""),
        PERSON_TIMEOUT=_env_int("PERSON_TIMEOUT", 5),
        MAX_TRACKED_PERSONS=_env_int("MAX_TRACKED_PERSONS", 50),
        ENTRY_LOG_SIZE=_env_int("ENTRY_LOG_SIZE", 100),
        DASHBOARD_PORT=_env_int("DASHBOARD_PORT", 8080),
        DASHBOARD_HOST=_env_str("DASHBOARD_HOST", "0.0.0.0"),
        CALIBRATION_FILE=_env_str("CALIBRATION_FILE", "calibration.json"),
        CAMERA_ID=_env_str("CAMERA_ID", "clinic_entrance_01"),
        LOG_LEVEL=_env_str("LOG_LEVEL", "INFO"),
    )


SETTINGS = load_settings()

# Backward-compatible constants for modules expecting constant values.
VIDEO_SOURCE = SETTINGS.VIDEO_SOURCE
WEBCAM_INDEX = SETTINGS.WEBCAM_INDEX
RTSP_URL = SETTINGS.RTSP_URL
VIDEO_FILE = SETTINGS.VIDEO_FILE
FRAME_WIDTH = SETTINGS.FRAME_WIDTH
FRAME_HEIGHT = SETTINGS.FRAME_HEIGHT
TARGET_FPS = SETTINGS.TARGET_FPS
YOLO_MODEL = SETTINGS.YOLO_MODEL
YOLO_CONFIDENCE = SETTINGS.YOLO_CONFIDENCE
YOLO_CLASSES = SETTINGS.YOLO_CLASSES
TRACKER = SETTINGS.TRACKER
YOLO_IMGSZ = SETTINGS.YOLO_IMGSZ
BBOX_GROWTH_RATIO = SETTINGS.BBOX_GROWTH_RATIO
Y_MOVEMENT_THRESHOLD = SETTINGS.Y_MOVEMENT_THRESHOLD
DWELL_TIME_MIN = SETTINGS.DWELL_TIME_MIN
DWELL_TIME_MAX = SETTINGS.DWELL_TIME_MAX
ENTRY_CONFIDENCE_THRESHOLD = SETTINGS.ENTRY_CONFIDENCE_THRESHOLD
TRAJECTORY_HISTORY_SECONDS = SETTINGS.TRAJECTORY_HISTORY_SECONDS
WEBHOOK_URL = SETTINGS.WEBHOOK_URL
WEBHOOK_TIMEOUT = SETTINGS.WEBHOOK_TIMEOUT
WEBHOOK_RETRY_COUNT = SETTINGS.WEBHOOK_RETRY_COUNT
WEBHOOK_RETRY_DELAY = SETTINGS.WEBHOOK_RETRY_DELAY
WEBHOOK_COOLDOWN_PERSON = SETTINGS.WEBHOOK_COOLDOWN_PERSON
WEBHOOK_COOLDOWN_GLOBAL = SETTINGS.WEBHOOK_COOLDOWN_GLOBAL
WEBHOOK_INCLUDE_SNAPSHOT = SETTINGS.WEBHOOK_INCLUDE_SNAPSHOT
WEBHOOK_SECRET = SETTINGS.WEBHOOK_SECRET
PERSON_TIMEOUT = SETTINGS.PERSON_TIMEOUT
MAX_TRACKED_PERSONS = SETTINGS.MAX_TRACKED_PERSONS
ENTRY_LOG_SIZE = SETTINGS.ENTRY_LOG_SIZE
DASHBOARD_PORT = SETTINGS.DASHBOARD_PORT
DASHBOARD_HOST = SETTINGS.DASHBOARD_HOST
CALIBRATION_FILE = SETTINGS.CALIBRATION_FILE
ZONE_B_SPLIT_RATIO = SETTINGS.ZONE_B_SPLIT_RATIO
MIN_ZONE_B_FRAMES = SETTINGS.MIN_ZONE_B_FRAMES
MIN_BBOX_AREA = SETTINGS.MIN_BBOX_AREA
