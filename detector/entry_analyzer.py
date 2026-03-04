"""Trajectory analyzer using dual polygon zones for robust entry/exit detection.

Uses Supervision's PolygonZone for spatial containment checks and tracks person
movement between an outer approach zone (Zone A) and inner entrance zone (Zone B).

Entry = person tracked in Zone A first, then appears in Zone B.
Exit  = person tracked in Zone B first, then appears in Zone A.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import supervision as sv

from .person_tracker import TrackedPerson
from .zone_config import CalibrationData


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class EntryEvent:
    event: str
    timestamp: str
    confidence: float
    person_id: int
    frame_number: int
    bbox: tuple[int, int, int, int]
    detection_details: dict[str, Any]


@dataclass(slots=True)
class PersonTrackState:
    person_id: int
    first_seen: float
    last_seen: float
    first_y: float
    first_x: float
    first_area: float
    positions: deque[tuple[float, float, float]] = field(default_factory=lambda: deque(maxlen=256))
    bbox_areas: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=256))
    in_entry_zone: bool = False
    crossed_tripwire: bool = False
    direction: str = "unknown"
    triggered: bool = False
    zone_entered_at: float | None = None
    zone_accumulated: float = 0.0
    last_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    last_confidence: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    score_total: float = 0.0
    entered_logged: bool = False
    exited_logged: bool = False
    passing_logged: bool = False
    flash_until: float = 0.0
    # Dual-zone tracking
    seen_in_zone_a: bool = False
    seen_in_zone_b: bool = False
    zone_a_first_ts: float | None = None
    zone_b_first_ts: float | None = None
    consecutive_zone_b_frames: int = 0
    _zone_b_miss_frames: int = 0
    total_zone_b_frames: int = 0  # lifetime count (not just consecutive)

    def current_dwell(self, now_ts: float) -> float:
        dwell = self.zone_accumulated
        if self.zone_entered_at is not None:
            dwell += max(0.0, now_ts - self.zone_entered_at)
        return dwell


def _build_zones(calibration: CalibrationData, split_ratio: float = 0.35) -> tuple[np.ndarray, np.ndarray]:
    """Build outer (Zone A) and inner (Zone B) polygon zones from calibration.

    Zone A = the full entry_zone rectangle (approach area).
    Zone B = the inner portion near the tripwire (actual entrance threshold).

    The split depends on entry_direction:
      - top_to_bottom: Zone B is bottom 35% of entry zone
      - bottom_to_top: Zone B is top 35% of entry zone
      - left_to_right: Zone B is right 35% of entry zone
      - right_to_left: Zone B is left 35% of entry zone
    """
    zone = calibration.entry_zone.normalized()
    x1, y1, x2, y2 = zone.x1, zone.y1, zone.x2, zone.y2
    direction = calibration.entry_direction

    # Zone A = full entry zone rectangle
    zone_a = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)

    # Zone B = inner portion (where person has committed to entering)
    split = split_ratio
    if direction == "top_to_bottom":
        split_y = int(y1 + (y2 - y1) * (1 - split))
        zone_b = np.array([[x1, split_y], [x2, split_y], [x2, y2], [x1, y2]], dtype=np.int32)
    elif direction == "bottom_to_top":
        split_y = int(y1 + (y2 - y1) * split)
        zone_b = np.array([[x1, y1], [x2, y1], [x2, split_y], [x1, split_y]], dtype=np.int32)
    elif direction == "left_to_right":
        split_x = int(x1 + (x2 - x1) * (1 - split))
        zone_b = np.array([[split_x, y1], [x2, y1], [x2, y2], [split_x, y2]], dtype=np.int32)
    else:  # right_to_left
        split_x = int(x1 + (x2 - x1) * split)
        zone_b = np.array([[x1, y1], [split_x, y1], [split_x, y2], [x1, y2]], dtype=np.int32)

    return zone_a, zone_b


class EntryAnalyzer:
    """Maintains track history and uses dual-zone logic for entry/exit detection."""

    def __init__(
        self,
        calibration: CalibrationData,
        settings: Any,
        logger: Any,
    ) -> None:
        self.calibration = calibration
        self.settings = settings
        self.logger = logger

        self.person_tracks: dict[int, PersonTrackState] = {}
        self.entry_log: deque[dict[str, Any]] = deque(maxlen=settings.ENTRY_LOG_SIZE)
        self.total_entries_today = 0
        self.last_entry_time: str | None = None
        self._last_entry_day = datetime.now(timezone.utc).date()

        # Counted IDs with expiry to prevent double-counting within cooldown
        # Maps person_id → timestamp of last entry event
        self._entered_ids: dict[int, float] = {}
        self._exited_ids: dict[int, float] = {}
        self._id_cooldown = float(settings.WEBHOOK_COOLDOWN_PERSON)  # reuse cooldown setting

        # Build zones from calibration
        self._rebuild_zones()

    def _rebuild_zones(self) -> None:
        """Rebuild supervision polygon zones from current calibration."""
        zone_a_poly, zone_b_poly = _build_zones(
            self.calibration,
            split_ratio=self.settings.ZONE_B_SPLIT_RATIO,
        )
        fw = self.calibration.frame_width
        fh = self.calibration.frame_height
        self.zone_a_polygon = zone_a_poly
        self.zone_b_polygon = zone_b_poly
        self.sv_zone_a = sv.PolygonZone(
            polygon=zone_a_poly,
            triggering_anchors=[sv.Position.BOTTOM_CENTER],
        )
        self.sv_zone_b = sv.PolygonZone(
            polygon=zone_b_poly,
            triggering_anchors=[sv.Position.BOTTOM_CENTER],
        )

    def _rotate_daily_counter_if_needed(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._last_entry_day:
            self.total_entries_today = 0
            self._last_entry_day = today
            self._entered_ids.clear()
            self._exited_ids.clear()

    def _id_in_cooldown(self, person_id: int, id_map: dict[int, float], now_ts: float) -> bool:
        """Check if person_id is still in cooldown. Expire old entries."""
        ts = id_map.get(person_id)
        if ts is None:
            return False
        if now_ts - ts > self._id_cooldown:
            del id_map[person_id]
            return False
        return True

    def _point_in_zone(self, x: float, y: float) -> bool:
        return self.calibration.entry_zone.contains(x, y)

    def _directional_movement(self, first_x: float, first_y: float, cur_x: float, cur_y: float) -> float:
        direction = self.calibration.entry_direction
        if direction == "top_to_bottom":
            return cur_y - first_y
        if direction == "bottom_to_top":
            return first_y - cur_y
        if direction == "left_to_right":
            return cur_x - first_x
        return first_x - cur_x

    def _tripwire_crossed_in_direction(
        self,
        prev_pt: tuple[float, float],
        cur_pt: tuple[float, float],
    ) -> bool:
        tw = self.calibration.tripwire
        x1, y1, x2, y2 = tw.x1, tw.y1, tw.x2, tw.y2
        px, py = prev_pt
        cx, cy = cur_pt

        def side(x: float, y: float) -> float:
            return (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)

        s_prev = side(px, py)
        s_cur = side(cx, cy)
        crossed = (s_prev == 0 or s_cur == 0) or (s_prev * s_cur < 0)
        if not crossed:
            return False

        direction = self.calibration.entry_direction
        if direction == "top_to_bottom":
            return cy > py
        if direction == "bottom_to_top":
            return cy < py
        if direction == "left_to_right":
            return cx > px
        return cx < px

    def _trim_history(self, state: PersonTrackState, now_ts: float) -> None:
        horizon = float(self.settings.TRAJECTORY_HISTORY_SECONDS)
        while state.positions and now_ts - state.positions[0][2] > horizon:
            state.positions.popleft()
        while state.bbox_areas and now_ts - state.bbox_areas[0][1] > horizon:
            state.bbox_areas.popleft()

    def _velocity_consistency(self, state: PersonTrackState) -> float:
        """Return 0.0-1.0 measuring how consistently the person moves in entry direction.

        Looks at the last N position samples and checks what fraction of
        consecutive steps move in the expected entry direction.
        """
        positions = state.positions
        if len(positions) < 4:
            return 0.0

        # Sample up to last 20 positions
        pts = list(positions)[-20:]
        forward_steps = 0
        total_steps = 0
        for i in range(1, len(pts)):
            prev_x, prev_y, _ = pts[i - 1]
            cur_x, cur_y, _ = pts[i]
            mv = self._directional_movement(prev_x, prev_y, cur_x, cur_y)
            total_steps += 1
            if mv > 0:
                forward_steps += 1

        return forward_steps / max(total_steps, 1)

    def _compute_scores(self, state: PersonTrackState, now_ts: float) -> tuple[float, dict[str, float], dict[str, float]]:
        empty_scores = {"bbox_size": 0.0, "y_movement": 0.0, "dwell_time": 0.0, "tripwire": 0.0, "zone_cross": 0.0, "velocity": 0.0}
        empty_metrics = {
            "bbox_growth_ratio": 1.0,
            "y_movement_pixels": 0.0,
            "dwell_time_seconds": 0.0,
            "entry_zone_time": 0.0,
            "velocity_consistency": 0.0,
            "track_age": 0.0,
        }
        if not state.bbox_areas or not state.positions:
            return 0.0, empty_scores, empty_metrics

        cur_area = state.bbox_areas[-1][0]
        ratio = cur_area / max(state.first_area, 1.0)
        cur_x, cur_y, _ = state.positions[-1]
        movement = self._directional_movement(state.first_x, state.first_y, cur_x, cur_y)
        dwell = state.current_dwell(now_ts)
        track_age = now_ts - state.first_seen
        vel_consistency = self._velocity_consistency(state)

        # --- Graduated scoring (partial credit) ---

        # Bbox growth: 0.0 → 0.25 (linear ramp from ratio 1.0 to threshold)
        bbox_thresh = self.settings.BBOX_GROWTH_RATIO
        if ratio >= bbox_thresh:
            bbox_score = 0.25
        elif ratio >= 1.0:
            bbox_score = 0.25 * (ratio - 1.0) / max(bbox_thresh - 1.0, 0.01)
        else:
            bbox_score = 0.0

        # Directional movement: 0.0 → 0.2 (linear ramp to threshold)
        mv_thresh = float(self.settings.Y_MOVEMENT_THRESHOLD)
        if movement >= mv_thresh:
            y_score = 0.2
        elif movement > 0:
            y_score = 0.2 * (movement / mv_thresh)
        else:
            y_score = 0.0

        # Dwell time: 0.0 → 0.1 (ramp from 0 to DWELL_TIME_MIN, then flat, then decay)
        dwell_min = self.settings.DWELL_TIME_MIN
        dwell_max = self.settings.DWELL_TIME_MAX
        if dwell_min <= dwell <= dwell_max:
            dwell_score = 0.1
        elif 0 < dwell < dwell_min:
            dwell_score = 0.1 * (dwell / dwell_min)
        else:
            dwell_score = 0.0

        # Tripwire (binary, small bonus)
        trip_score = 0.1 if state.crossed_tripwire else 0.0

        # Zone crossing: graduated by consecutive Zone B frames (0.0 → 0.25)
        zone_cross_score = 0.0
        min_b_frames = self.settings.MIN_ZONE_B_FRAMES
        if state.seen_in_zone_a and state.seen_in_zone_b:
            # Must have seen Zone A before Zone B (temporal ordering)
            a_ts = state.zone_a_first_ts or now_ts
            b_ts = state.zone_b_first_ts or now_ts
            if a_ts <= b_ts:
                b_frames = state.consecutive_zone_b_frames
                if b_frames >= min_b_frames:
                    zone_cross_score = 0.25
                elif b_frames > 0:
                    zone_cross_score = 0.25 * (b_frames / min_b_frames)

        # Velocity consistency: 0.0 → 0.1 (requires >50% forward steps)
        vel_score = 0.0
        if vel_consistency >= 0.5:
            vel_score = 0.1 * min(1.0, (vel_consistency - 0.5) / 0.3)

        score_total = bbox_score + y_score + dwell_score + trip_score + zone_cross_score + vel_score

        direction_scores = {
            "bbox_size": round(bbox_score, 4),
            "y_movement": round(y_score, 4),
            "dwell_time": round(dwell_score, 4),
            "tripwire": round(trip_score, 4),
            "zone_cross": round(zone_cross_score, 4),
            "velocity": round(vel_score, 4),
        }
        metrics = {
            "bbox_growth_ratio": round(float(ratio), 4),
            "y_movement_pixels": round(float(movement), 2),
            "dwell_time_seconds": round(float(dwell), 2),
            "entry_zone_time": round(float(dwell), 2),
            "velocity_consistency": round(float(vel_consistency), 3),
            "track_age": round(float(track_age), 2),
        }
        return score_total, direction_scores, metrics

    def _classify(self, state: PersonTrackState, score: float, metrics: dict[str, float]) -> str:
        ratio = metrics["bbox_growth_ratio"]
        movement = metrics["y_movement_pixels"]
        dwell = metrics["dwell_time_seconds"]
        track_age = metrics.get("track_age", 0.0)
        vel_consistency = metrics.get("velocity_consistency", 0.0)

        # Hard guard: track must be at least 0.5s old to prevent instant triggers
        if track_age < 0.5:
            return "unknown"

        # Primary: dual-zone crossing (Zone A → Zone B with temporal ordering)
        if (
            state.seen_in_zone_a
            and state.seen_in_zone_b
            and state.consecutive_zone_b_frames >= self.settings.MIN_ZONE_B_FRAMES
            and (state.zone_a_first_ts or 0) <= (state.zone_b_first_ts or 0)
            and score >= self.settings.ENTRY_CONFIDENCE_THRESHOLD
            and dwell <= self.settings.DWELL_TIME_MAX
            and vel_consistency >= 0.3
        ):
            return "entering"

        # Fallback: tripwire + high score + velocity confirmation
        if (
            score >= self.settings.ENTRY_CONFIDENCE_THRESHOLD + 0.1
            and state.crossed_tripwire
            and dwell <= self.settings.DWELL_TIME_MAX
            and track_age >= 1.0
            and vel_consistency >= 0.4
        ):
            return "entering"

        if ratio <= 0.85 and movement <= -self.settings.Y_MOVEMENT_THRESHOLD * 0.5:
            return "exiting"

        if dwell < self.settings.DWELL_TIME_MIN and abs(movement) < self.settings.Y_MOVEMENT_THRESHOLD * 0.5:
            return "passing"

        if dwell > self.settings.DWELL_TIME_MAX:
            return "loitering"

        return "unknown"

    def _make_event(
        self,
        event_name: str,
        state: PersonTrackState,
        frame_number: int,
        score: float,
        metrics: dict[str, float],
        scores: dict[str, float],
    ) -> EntryEvent:
        details = {
            **metrics,
            "direction_scores": scores,
        }
        return EntryEvent(
            event=event_name,
            timestamp=_utc_now_iso(),
            confidence=round(score, 4),
            person_id=state.person_id,
            frame_number=frame_number,
            bbox=state.last_bbox,
            detection_details=details,
        )

    def _enforce_track_cap(self) -> None:
        limit = int(self.settings.MAX_TRACKED_PERSONS)
        if len(self.person_tracks) <= limit:
            return

        ordered = sorted(self.person_tracks.values(), key=lambda s: s.last_seen)
        for state in ordered:
            if len(self.person_tracks) <= limit:
                break
            self.person_tracks.pop(state.person_id, None)

    def _check_zones_for_detections(self, detections: list[TrackedPerson]) -> dict[int, tuple[bool, bool]]:
        """Check which detections are in Zone A and Zone B using Supervision."""
        if not detections:
            return {}

        # Build arrays for Supervision
        xyxy = np.array([d.bbox for d in detections], dtype=np.float32)
        confidence = np.array([d.confidence for d in detections], dtype=np.float32)
        tracker_ids = np.array([d.person_id for d in detections], dtype=int)

        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            tracker_id=tracker_ids,
        )

        in_zone_a = self.sv_zone_a.trigger(detections=sv_detections)
        in_zone_b = self.sv_zone_b.trigger(detections=sv_detections)

        result = {}
        for i, det in enumerate(detections):
            result[det.person_id] = (bool(in_zone_a[i]), bool(in_zone_b[i]))

        return result

    def update(
        self,
        detections: list[TrackedPerson],
        now_ts: float,
        frame_number: int,
    ) -> list[EntryEvent]:
        """Update trajectories with current detections and emit new events."""
        self._rotate_daily_counter_if_needed()

        # Check zone membership for all detections at once
        zone_membership = self._check_zones_for_detections(detections)

        events: list[EntryEvent] = []
        seen_ids: set[int] = set()

        for detection in detections:
            person_id = detection.person_id
            seen_ids.add(person_id)
            cx, cy = detection.center_bottom
            area = max(1.0, float((detection.bbox[2] - detection.bbox[0]) * (detection.bbox[3] - detection.bbox[1])))
            if area < self.settings.MIN_BBOX_AREA:
                continue
            in_zone_a, in_zone_b = zone_membership.get(person_id, (False, False))
            in_zone = in_zone_a or in_zone_b  # backwards compat

            state = self.person_tracks.get(person_id)
            if state is None:
                # New tracks begin only when person enters either zone
                if not in_zone:
                    continue
                state = PersonTrackState(
                    person_id=person_id,
                    first_seen=now_ts,
                    last_seen=now_ts,
                    first_x=cx,
                    first_y=cy,
                    first_area=area,
                )
                self.person_tracks[person_id] = state

            prev_pos = state.positions[-1] if state.positions else None
            state.last_seen = now_ts
            state.last_bbox = detection.bbox
            state.last_confidence = detection.confidence
            state.in_entry_zone = in_zone
            state.positions.append((cx, cy, now_ts))
            state.bbox_areas.append((area, now_ts))
            self._trim_history(state, now_ts)

            # Dwell tracking
            if in_zone and state.zone_entered_at is None:
                state.zone_entered_at = now_ts
            if not in_zone and state.zone_entered_at is not None:
                state.zone_accumulated += max(0.0, now_ts - state.zone_entered_at)
                state.zone_entered_at = None

            # Tripwire check (legacy, still contributes to score)
            if prev_pos is not None:
                crossed = self._tripwire_crossed_in_direction(
                    prev_pt=(prev_pos[0], prev_pos[1]),
                    cur_pt=(cx, cy),
                )
                if crossed:
                    state.crossed_tripwire = True

            # Dual-zone tracking
            if in_zone_a and not state.seen_in_zone_a:
                state.seen_in_zone_a = True
                state.zone_a_first_ts = now_ts

            if in_zone_b:
                if not state.seen_in_zone_b:
                    state.seen_in_zone_b = True
                    state.zone_b_first_ts = now_ts
                state.consecutive_zone_b_frames += 1
                state.total_zone_b_frames += 1
                state._zone_b_miss_frames = 0
            else:
                # Allow 2 frames of jitter before resetting — bbox can flicker
                miss = getattr(state, "_zone_b_miss_frames", 0) + 1
                state._zone_b_miss_frames = miss
                if miss > 2:
                    state.consecutive_zone_b_frames = 0

            # Compute scores and classify
            score_total, score_breakdown, metrics = self._compute_scores(state, now_ts)
            state.score_total = score_total
            state.score_breakdown = score_breakdown

            classification = self._classify(state, score_total, metrics)
            state.direction = classification

            if classification == "entering" and not state.entered_logged:
                # Deduplicate: don't count same ID within cooldown window
                if self._id_in_cooldown(person_id, self._entered_ids, now_ts):
                    state.entered_logged = True
                    continue

                state.entered_logged = True
                state.triggered = True
                state.flash_until = now_ts + 2.0
                self._entered_ids[person_id] = now_ts

                event = self._make_event(
                    "person_entered",
                    state,
                    frame_number,
                    score_total,
                    metrics,
                    score_breakdown,
                )
                events.append(event)
                self.total_entries_today += 1
                self.last_entry_time = event.timestamp
                self.entry_log.append(
                    {
                        "event": event.event,
                        "timestamp": event.timestamp,
                        "person_id": event.person_id,
                        "confidence": event.confidence,
                        "details": event.detection_details,
                    }
                )
                self.logger.info(
                    "Entry detected (dual-zone)",
                    extra={
                        "extra": {
                            "person_id": event.person_id,
                            "confidence": event.confidence,
                            "zone_a_seen": state.seen_in_zone_a,
                            "zone_b_frames": state.consecutive_zone_b_frames,
                            "tripwire_crossed": state.crossed_tripwire,
                            "details": event.detection_details,
                        }
                    },
                )
            elif classification == "exiting" and not state.exited_logged:
                state.exited_logged = True
                event = self._make_event(
                    "person_exited",
                    state,
                    frame_number,
                    score_total,
                    metrics,
                    score_breakdown,
                )
                events.append(event)
            elif classification == "passing" and not state.passing_logged:
                state.passing_logged = True

        stale_ids: list[int] = []
        for person_id, state in self.person_tracks.items():
            if person_id in seen_ids:
                continue
            if now_ts - state.last_seen > self.settings.PERSON_TIMEOUT:
                stale_ids.append(person_id)

        for person_id in stale_ids:
            self.person_tracks.pop(person_id, None)

        self._enforce_track_cap()
        return events

    def recent_entries(self) -> list[dict[str, Any]]:
        return list(self.entry_log)

    def current_people(self) -> int:
        return len(self.person_tracks)

    def active_states(self) -> list[PersonTrackState]:
        return list(self.person_tracks.values())
