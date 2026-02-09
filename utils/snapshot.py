"""Snapshot helper utilities for webhook payload attachments."""

from __future__ import annotations

import base64
from typing import Sequence

import cv2
import numpy as np


def _resize_with_aspect(image: np.ndarray, target_width: int) -> np.ndarray:
    h, w = image.shape[:2]
    if w <= target_width:
        return image
    ratio = target_width / float(w)
    target_height = int(h * ratio)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def encode_snapshot_base64(
    frame: np.ndarray,
    bbox: Sequence[int] | None = None,
    target_width: int = 640,
    jpeg_quality: int = 70,
) -> str:
    """Encode frame to compressed base64 JPEG with optional bbox highlight."""
    canvas = frame.copy()
    if bbox is not None and len(bbox) == 4:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
    canvas = _resize_with_aspect(canvas, target_width)
    ok, buffer = cv2.imencode(
        ".jpg",
        canvas,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
    )
    if not ok:
        return ""
    return base64.b64encode(buffer.tobytes()).decode("utf-8")
