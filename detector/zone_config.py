"""Zone and tripwire calibration configuration management."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal


EntryDirection = Literal["top_to_bottom", "bottom_to_top", "left_to_right", "right_to_left"]


@dataclass(slots=True)
class Point:
    x: int
    y: int


@dataclass(slots=True)
class EntryZone:
    x1: int
    y1: int
    x2: int
    y2: int

    def normalized(self) -> "EntryZone":
        return EntryZone(
            x1=min(self.x1, self.x2),
            y1=min(self.y1, self.y2),
            x2=max(self.x1, self.x2),
            y2=max(self.y1, self.y2),
        )

    def contains(self, x: float, y: float) -> bool:
        zone = self.normalized()
        return zone.x1 <= x <= zone.x2 and zone.y1 <= y <= zone.y2


@dataclass(slots=True)
class Tripwire:
    x1: int
    y1: int
    x2: int
    y2: int

    def points(self) -> tuple[Point, Point]:
        return Point(self.x1, self.y1), Point(self.x2, self.y2)


@dataclass(slots=True)
class CalibrationData:
    entry_zone: EntryZone
    tripwire: Tripwire
    entry_direction: EntryDirection
    frame_width: int
    frame_height: int
    calibrated_at: str

    @classmethod
    def default(cls, width: int = 1280, height: int = 720) -> "CalibrationData":
        zone = EntryZone(int(width * 0.3), int(height * 0.2), int(width * 0.7), int(height * 0.95))
        y = int(height * 0.4)
        trip = Tripwire(zone.x1, y, zone.x2, y)
        return cls(
            entry_zone=zone,
            tripwire=trip,
            entry_direction="top_to_bottom",
            frame_width=width,
            frame_height=height,
            calibrated_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationData":
        entry_direction: EntryDirection = str(data.get("entry_direction", "top_to_bottom"))  # type: ignore[assignment]
        if entry_direction not in {"top_to_bottom", "bottom_to_top", "left_to_right", "right_to_left"}:
            entry_direction = "top_to_bottom"

        return cls(
            entry_zone=EntryZone(**data["entry_zone"]),
            tripwire=Tripwire(**data["tripwire"]),
            entry_direction=entry_direction,
            frame_width=int(data.get("frame_width", 1280)),
            frame_height=int(data.get("frame_height", 720)),
            calibrated_at=str(data.get("calibrated_at", datetime.now(timezone.utc).isoformat())),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entry_zone"] = asdict(self.entry_zone.normalized())
        return payload


class ZoneConfigManager:
    """Loads and stores calibration data for entry zone and tripwire."""

    def __init__(self, calibration_path: str | Path) -> None:
        self.calibration_path = Path(calibration_path)
        self.calibration: CalibrationData | None = None

    def load(self) -> CalibrationData:
        if not self.calibration_path.exists():
            self.calibration = CalibrationData.default()
            self.save(self.calibration)
            return self.calibration

        with self.calibration_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.calibration = CalibrationData.from_dict(data)
        return self.calibration

    def save(self, calibration: CalibrationData) -> None:
        calibration.calibrated_at = datetime.now(timezone.utc).isoformat()
        self.calibration = calibration
        self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
        with self.calibration_path.open("w", encoding="utf-8") as fp:
            json.dump(calibration.to_dict(), fp, indent=2)

    def update(
        self,
        entry_zone: EntryZone | None = None,
        tripwire: Tripwire | None = None,
        entry_direction: EntryDirection | None = None,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> CalibrationData:
        calibration = self.calibration or self.load()
        if entry_zone is not None:
            calibration.entry_zone = entry_zone
        if tripwire is not None:
            calibration.tripwire = tripwire
        if entry_direction is not None:
            calibration.entry_direction = entry_direction
        if frame_width is not None:
            calibration.frame_width = frame_width
        if frame_height is not None:
            calibration.frame_height = frame_height
        self.save(calibration)
        return calibration

    @property
    def current(self) -> CalibrationData:
        if self.calibration is None:
            return self.load()
        return self.calibration
