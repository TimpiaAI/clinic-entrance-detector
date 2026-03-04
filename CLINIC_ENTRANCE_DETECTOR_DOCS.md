# Clinic Entrance Detection System
## Comprehensive Technical Documentation

**Version:** 1.0
**Last Updated:** 2026-02-10
**Document Type:** Technical Architecture & Implementation Reference

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Detection Pipeline Deep Dive](#4-detection-pipeline-deep-dive)
5. [Dual-Zone Detection System](#5-dual-zone-detection-system)
6. [Graduated Scoring Algorithm](#6-graduated-scoring-algorithm)
7. [Classification Logic](#7-classification-logic)
8. [Person Tracking & Anti-Duplication](#8-person-tracking--anti-duplication)
9. [Zone Calibration](#9-zone-calibration)
10. [Dashboard & Monitoring](#10-dashboard--monitoring)
11. [Webhook System](#11-webhook-system)
12. [Configuration Reference](#12-configuration-reference)
13. [Video Source Management](#13-video-source-management)
14. [Training & Fine-Tuning](#14-training--fine-tuning)
15. [File & Module Reference](#15-file--module-reference)
16. [Installation & Setup](#16-installation--setup)
17. [CLI Reference](#17-cli-reference)
18. [Known Limitations & Future Improvements](#18-known-limitations--future-improvements)

---

## 1. Executive Summary

### What Is This System?

The Clinic Entrance Detection System is a production-grade computer vision application that detects and counts people entering a clinic through real-time video analysis. It runs on commodity hardware (CPU or GPU), supports multiple video sources (webcam, RTSP, video file), and delivers entry events via webhooks with snapshots.

### Key Capabilities

- **Real-Time Person Detection**: YOLOv8m at 1280px resolution with tuned BoT-SORT tracking
- **Dual-Zone Spatial Analysis**: Distinguishes genuine entries from passing traffic using graduated zone-based logic
- **Anti-Duplication**: Prevents counting the same person multiple times within a 30-second cooldown
- **Webhook Delivery**: Async delivery with retries, HMAC signatures, and failure persistence
- **Web Dashboard**: Live video feed, metrics, calibration interface, and event log
- **Fine-Tuning Support**: Dataset collection and YOLO fine-tuning for environment-specific optimization

### Target Audience

This documentation is designed for:
- Software engineers implementing or maintaining the system
- DevOps teams deploying to production environments
- Data scientists fine-tuning detection models
- System architects evaluating the design

---

## 2. System Overview

### Problem Statement

Traditional people counting systems suffer from:
- **False positives** from people passing by the entrance
- **False negatives** from occlusion or poor camera angles
- **Double counting** when people linger near the entrance
- **High computational cost** requiring expensive hardware

This system solves these problems using a dual-zone approach with graduated scoring, allowing accurate entry detection even in challenging scenarios (crowds, occlusion, varying lighting).

### Design Philosophy

1. **Graduated Detection**: Partial credit for ambiguous movements rather than binary thresholds
2. **Spatial Reasoning**: Entry requires Zone A → Zone B spatial ordering, not just tripwire crossing
3. **Temporal Consistency**: Requires sustained presence in Zone B (≥5 frames) to filter jitter
4. **Fail-Safe Defaults**: Conservative detection reduces false positives at the cost of occasional false negatives

### System Boundaries

**In Scope:**
- Person detection and tracking
- Entry/exit/passing/loitering classification
- Webhook delivery with retry logic
- Web dashboard for monitoring
- Calibration tools
- Model fine-tuning

**Out of Scope:**
- Face recognition or identification
- Multi-camera fusion
- Historical analytics beyond daily counters
- Database integration (webhook consumers handle persistence)

---

## 3. Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VIDEO SOURCE                                    │
│              (Webcam / RTSP Stream / Video File)                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      VideoStream (Threaded Reader)                      │
│  • Background thread reads frames at TARGET_FPS                         │
│  • Thread-safe frame buffer with lock                                   │
│  • EOF detection for video files                                        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ frame (numpy array)
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  PersonTracker (YOLOv8 + BoT-SORT)                      │
│  • YOLOv8m inference at 1280px resolution                               │
│  • BoT-SORT tracking with tuned parameters                              │
│  • Persistent track IDs across frames                                   │
│  • Outputs: List[TrackedPerson]                                         │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ List[TrackedPerson]
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    EntryAnalyzer (Dual-Zone Logic)                      │
│  • Zone A (approach) vs Zone B (inner) containment checks               │
│  • Graduated scoring: bbox growth, movement, dwell, velocity            │
│  • Classification: entering/exiting/passing/loitering                   │
│  • Anti-duplication: cooldown-based ID tracking                         │
│  • Outputs: List[EntryEvent]                                            │
└─────────────────────┬────────────────────────┬──────────────────────────┘
                      │                        │
      ┌───────────────▼─────────┐   ┌──────────▼────────────┐
      │  WebhookSender          │   │  DashboardState       │
      │  • Async delivery       │   │  • Frame JPEG buffer  │
      │  • Retry w/ backoff     │   │  • Metrics snapshot   │
      │  • Per-person cooldown  │   │  • Event log          │
      │  • HMAC signature       │   └──────────┬────────────┘
      │  • Failure persistence  │              │
      └─────────────────────────┘              │
                                               ▼
                                     ┌───────────────────────┐
                                     │  FastAPI Dashboard    │
                                     │  • /video_feed (MJPEG)│
                                     │  • /ws (WebSocket)    │
                                     │  • /calibrate (UI)    │
                                     │  • /api/* (REST)      │
                                     └───────────────────────┘
```

### Module Relationships

```
main.py
├── config.py (Settings dataclass)
├── detector/
│   ├── person_tracker.py (YOLO + BoT-SORT)
│   ├── entry_analyzer.py (dual-zone detection)
│   └── zone_config.py (calibration data models)
├── webhook/
│   └── sender.py (async webhook delivery)
├── dashboard/
│   └── web.py (FastAPI app + state manager)
├── utils/
│   ├── video_stream.py (threaded capture)
│   ├── logger.py (JSON logging)
│   └── snapshot.py (base64 JPEG encoder)
├── calibration/
│   └── calibration_tool.py (interactive OpenCV UI)
└── training/
    ├── data_collector.py (dataset builder)
    └── trainer.py (fine-tuning wrapper)
```

### Data Flow

1. **Frame Acquisition**: VideoStream reads frames in background thread
2. **Detection**: PersonTracker runs YOLOv8 inference + tracking
3. **Analysis**: EntryAnalyzer updates per-person state, emits events
4. **Delivery**: WebhookSender queues events with cooldown checks
5. **Visualization**: Main loop overlays zones/boxes, updates dashboard
6. **Monitoring**: Dashboard serves live feed + metrics via HTTP/WebSocket

---

## 4. Detection Pipeline Deep Dive

### 4.1 Person Detection: YOLOv8m

**Model**: YOLOv8m (medium variant, ~26M parameters)
**Resolution**: 1280px (high-res mode for better small person detection)
**Confidence Threshold**: 0.4 (default, configurable)
**Classes**: [0] (person class from COCO dataset)

**Why YOLOv8m?**
- Balances accuracy vs. speed (15-30 FPS on CPU, 60+ FPS on GPU)
- Excellent small object detection at 1280px resolution
- Pretrained on COCO with robust person detection
- Supports fine-tuning for domain adaptation

**Inference Process** (PersonTracker.track):
```python
results = model.track(
    frame,
    persist=True,        # Enable tracking memory
    conf=0.4,            # Min confidence
    classes=[0],         # Person only
    tracker="botsort_tuned.yaml",
    imgsz=1280,          # High-res inference
    verbose=False
)
```

**Output**: List of bounding boxes with persistent track IDs

### 4.2 Tracking: BoT-SORT (Tuned)

**Tracker**: BoT-SORT (Kalman filter + appearance ReID)
**Tuning Philosophy**: Stricter initialization, longer buffer, camera motion compensation

**Key Parameters** (vs. defaults):

| Parameter           | Default | Tuned | Rationale                                    |
|---------------------|---------|-------|----------------------------------------------|
| track_high_thresh   | 0.25    | 0.35  | Stricter first-stage match reduces ID switches |
| track_low_thresh    | 0.1     | 0.15  | Less noise from weak detections              |
| new_track_thresh    | 0.25    | 0.4   | Don't start tracks on weak detections        |
| track_buffer        | 30      | 45    | Keep lost tracks longer through occlusion    |
| match_thresh        | 0.8     | 0.75  | More willing to match existing tracks        |
| gmc_method          | None    | sparseOptFlow | Camera motion compensation           |

**Benefits of Tuned Config**:
- Reduces ID switches when people briefly occluded
- Filters transient false detections (shadows, reflections)
- Maintains stable IDs for 2-3 seconds of occlusion

**File**: `botsort_tuned.yaml` (loaded by PersonTracker)

### 4.3 TrackedPerson Data Model

```python
@dataclass
class TrackedPerson:
    person_id: int              # Persistent track ID
    bbox: (x1, y1, x2, y2)     # Bounding box
    confidence: float           # Detection confidence (0-1)
    center_bottom: (cx, cy)     # Bottom-center anchor point
    frame_number: int           # Frame index
    timestamp: float            # Unix timestamp
```

**Why Bottom-Center Anchor?**
- Feet position is stable for spatial containment checks
- Less affected by head/torso occlusion
- Natural ground-plane reference for zone membership

---

## 5. Dual-Zone Detection System

### 5.1 Conceptual Model

Traditional tripwire-based systems fail to distinguish genuine entries from:
- People passing by the entrance
- People loitering near the entrance
- Camera jitter causing false crossings

**Solution**: Dual-zone approach with temporal ordering

```
┌────────────────────────────────────────┐
│         ZONE A (Approach Area)         │  ← Outer zone
│  ┌────────────────────────────────┐    │
│  │    ZONE B (Commitment Zone)    │    │  ← Inner zone (35% of Zone A)
│  │          (35% of A)             │    │
│  │                                 │    │
│  │  ════════════════════════════   │    │  ← Tripwire (legacy, bonus signal)
│  │                                 │    │
│  └────────────────────────────────┘    │
└────────────────────────────────────────┘

Entry = Person appears in Zone A FIRST, then moves to Zone B
      + Sustained presence in Zone B (≥5 consecutive frames)
      + Score ≥ threshold (default 0.5)
```

### 5.2 Zone Construction

Zones are built from `CalibrationData.entry_zone` (rectangle) and split based on `entry_direction`:

**Top-to-Bottom Entry** (default):
- Zone A = full entry_zone rectangle
- Zone B = bottom 35% of entry_zone (near floor/exit)

**Bottom-to-Top Entry**:
- Zone A = full entry_zone
- Zone B = top 35% of entry_zone

**Left-to-Right Entry**:
- Zone A = full entry_zone
- Zone B = right 35% of entry_zone

**Right-to-Left Entry**:
- Zone A = full entry_zone
- Zone B = left 35% of entry_zone

**Implementation** (`_build_zones` in entry_analyzer.py:79):
```python
split = 0.35  # Zone B is inner 35%
if direction == "top_to_bottom":
    split_y = int(y1 + (y2 - y1) * (1 - split))
    zone_b = [[x1, split_y], [x2, split_y], [x2, y2], [x1, y2]]
# ... (similar for other directions)
```

### 5.3 Zone Membership Checks

**Library**: Supervision's `PolygonZone` with `BOTTOM_CENTER` anchor

```python
self.sv_zone_a = sv.PolygonZone(
    polygon=zone_a_poly,
    triggering_anchors=[sv.Position.BOTTOM_CENTER]
)
self.sv_zone_b = sv.PolygonZone(
    polygon=zone_b_poly,
    triggering_anchors=[sv.Position.BOTTOM_CENTER]
)
```

**Per-Frame Update** (entry_analyzer.py:380):
1. Check if person's bottom-center is in Zone A
2. Check if person's bottom-center is in Zone B
3. Update `PersonTrackState` flags:
   - `seen_in_zone_a`, `seen_in_zone_b`
   - `zone_a_first_ts`, `zone_b_first_ts` (timestamps)
   - `consecutive_zone_b_frames` (counter with jitter tolerance)

### 5.4 Temporal Ordering Enforcement

**Entry Requirement**: Zone A must be seen BEFORE Zone B

```python
if state.zone_a_first_ts is not None and state.zone_b_first_ts is not None:
    if state.zone_a_first_ts < state.zone_b_first_ts:
        # Valid temporal order for entry
        zone_cross_score = graduated_score_based_on_consecutive_frames
```

**Why This Matters**:
- Filters people exiting (they appear in Zone B first)
- Filters people teleporting into Zone B (camera occlusion)
- Ensures directionality matches configured entry_direction

---

## 6. Graduated Scoring Algorithm

### 6.1 Philosophy

Traditional binary thresholds (tripwire crossed = entry) create:
- **False positives** from brief crossings
- **False negatives** from occlusion at the exact tripwire moment
- **No confidence measure** for ambiguous cases

**Solution**: Graduated scoring gives partial credit to multiple signals:
- Bbox size increase (approaching camera)
- Directional movement
- Dwell time in entry zone
- Tripwire crossing (bonus)
- Zone crossing consistency
- Velocity consistency

**Total Score Range**: 0.0 to 1.0
**Default Threshold**: 0.5 (configurable via `ENTRY_CONFIDENCE_THRESHOLD`)

### 6.2 Score Components

#### 6.2.1 Bbox Size (Weight: 0.25 max)

**Signal**: Person approaching camera has growing bounding box area

```python
ratio = current_bbox_area / first_bbox_area
bbox_thresh = 1.3  # Default BBOX_GROWTH_RATIO

if ratio >= bbox_thresh:
    bbox_score = 0.25
elif ratio >= 1.0:
    bbox_score = 0.25 * (ratio - 1.0) / (bbox_thresh - 1.0)
else:
    bbox_score = 0.0
```

**Example**:
- Ratio 1.0 (no growth) → 0.0
- Ratio 1.15 (15% growth) → 0.125
- Ratio 1.3+ (30%+ growth) → 0.25

#### 6.2.2 Directional Movement (Weight: 0.2 max)

**Signal**: Movement in configured entry_direction (e.g., Y-axis for top_to_bottom)

```python
movement = current_y - first_y  # For top_to_bottom
mv_thresh = 50  # Default Y_MOVEMENT_THRESHOLD (pixels)

if movement >= mv_thresh:
    y_score = 0.2
elif movement > 0:
    y_score = 0.2 * (movement / mv_thresh)
else:
    y_score = 0.0
```

**Example** (top_to_bottom):
- Movement 0px → 0.0
- Movement 25px → 0.1
- Movement 50px+ → 0.2

#### 6.2.3 Dwell Time (Weight: 0.1 max)

**Signal**: Person spends appropriate time in entry zone (not too brief, not too long)

```python
dwell_min = 1.5   # Default DWELL_TIME_MIN (seconds)
dwell_max = 15.0  # Default DWELL_TIME_MAX (seconds)

if dwell_min <= dwell <= dwell_max:
    dwell_score = 0.1
elif 0 < dwell < dwell_min:
    dwell_score = 0.1 * (dwell / dwell_min)
else:
    dwell_score = 0.0  # Too long = loitering
```

**Example**:
- Dwell 0.5s → 0.033
- Dwell 1.5s → 0.1
- Dwell 10s → 0.1
- Dwell 20s → 0.0 (too long)

#### 6.2.4 Tripwire Crossing (Weight: 0.1 max, binary)

**Signal**: Legacy tripwire line crossed in entry direction

```python
if state.crossed_tripwire:
    tripwire_score = 0.1
else:
    tripwire_score = 0.0
```

**Crossing Detection**: Line-segment intersection test with direction check

**Note**: Tripwire is supplementary; Zone B logic is primary

#### 6.2.5 Zone Crossing (Weight: 0.25 max)

**Signal**: Sustained presence in Zone B with temporal ordering

```python
if temporal_order_valid and consecutive_zone_b_frames >= 5:
    zone_cross_score = 0.25
elif temporal_order_valid and consecutive_zone_b_frames > 0:
    zone_cross_score = 0.25 * (consecutive_zone_b_frames / 5.0)
else:
    zone_cross_score = 0.0
```

**Jitter Tolerance**: 2 frames of Zone B miss allowed before resetting consecutive count

**Example**:
- 2 consecutive frames in Zone B → 0.1
- 5+ consecutive frames in Zone B → 0.25
- Zone B → Zone A → Zone B (miss tolerance) → still counts consecutive

#### 6.2.6 Velocity Consistency (Weight: 0.1 max)

**Signal**: Majority of movement steps are in entry direction

```python
forward_ratio = forward_steps / total_steps  # Last 20 position samples

if forward_ratio >= 0.8:
    velocity_score = 0.1
elif forward_ratio >= 0.5:
    velocity_score = 0.1 * (forward_ratio - 0.5) / 0.3
else:
    velocity_score = 0.0
```

**Purpose**: Filters erratic movement (passing, loitering) from directed entry movement

### 6.3 Score Calculation Flow

**Implementation** (`_compute_scores` in entry_analyzer.py:250):

```python
def _compute_scores(state, now_ts):
    # 1. Extract metrics
    bbox_ratio = current_area / first_area
    movement = directional_delta(first_pos, current_pos)
    dwell = current_dwell_time(now_ts)
    vel_consistency = velocity_consistency(state)

    # 2. Compute graduated scores
    bbox_score = graduated_bbox_score(bbox_ratio)
    y_score = graduated_movement_score(movement)
    dwell_score = graduated_dwell_score(dwell)
    tripwire_score = 0.1 if state.crossed_tripwire else 0.0
    zone_cross_score = graduated_zone_score(state)
    velocity_score = graduated_velocity_score(vel_consistency)

    # 3. Sum to total
    total_score = (bbox_score + y_score + dwell_score +
                   tripwire_score + zone_cross_score + velocity_score)

    return total_score, score_breakdown, metrics
```

**Score Breakdown** (returned for debugging):
```json
{
  "bbox_size": 0.25,
  "y_movement": 0.15,
  "dwell_time": 0.1,
  "tripwire": 0.1,
  "zone_cross": 0.25,
  "velocity": 0.08
}
```

---

## 7. Classification Logic

### 7.1 Classification States

Each tracked person has a `direction` field with possible values:

| State       | Meaning                              | Color     | Description                                    |
|-------------|--------------------------------------|-----------|------------------------------------------------|
| `entering`  | Person is entering the clinic        | Green     | Score ≥ threshold, Zone A→B order, sustained   |
| `exiting`   | Person is exiting the clinic         | Blue      | Bbox shrinking + reverse movement              |
| `passing`   | Person passed by without entering    | Gray      | Short dwell + minimal movement                 |
| `loitering` | Person lingering near entrance       | N/A       | Dwell > DWELL_TIME_MAX                         |
| `unknown`   | Initial state, still analyzing       | Orange    | Not enough data yet                            |

### 7.2 Entry Classification Rules

**Primary Rule** (entry_analyzer.py:455):
```python
if (
    state.seen_in_zone_a and state.seen_in_zone_b and
    state.zone_a_first_ts < state.zone_b_first_ts and  # Temporal order
    state.consecutive_zone_b_frames >= 5 and           # Sustained presence
    score >= ENTRY_CONFIDENCE_THRESHOLD and            # Score threshold
    vel_consistency >= 0.3 and                         # Not erratic
    track_age >= 0.5                                   # Minimum track age
):
    return "entering"
```

**Fallback Rule** (for edge cases where Zone B jitter):
```python
if (
    state.crossed_tripwire and
    score >= (ENTRY_CONFIDENCE_THRESHOLD + 0.1) and  # Higher threshold
    track_age >= 1.0 and                             # Longer track
    vel_consistency >= 0.4                           # More consistent
):
    return "entering"
```

**Why Both Rules?**
- Primary rule is robust for normal cases
- Fallback handles occlusion at Zone B boundary (e.g., doorframe)

### 7.3 Exit Classification

```python
if (
    ratio < 0.85 and                    # Bbox shrinking by 15%+
    movement < -20 and                  # Reverse movement
    track_age >= 1.0
):
    return "exiting"
```

**Note**: Exit events are NOT sent to webhook (can be changed if needed)

### 7.4 Passing Classification

```python
if (
    dwell < (DWELL_TIME_MIN * 0.8) and  # Very short dwell
    abs(movement) < 30 and              # Minimal net movement
    track_age >= 1.5
):
    return "passing"
```

**Purpose**: Filters people walking past the entrance without entering

### 7.5 Loitering Classification

```python
if dwell > DWELL_TIME_MAX:
    return "loitering"
```

**Purpose**: Identifies people lingering (waiting, talking) near entrance

---

## 8. Person Tracking & Anti-Duplication

### 8.1 PersonTrackState Data Model

**Full State** (entry_analyzer.py:39):
```python
@dataclass
class PersonTrackState:
    person_id: int                # Persistent track ID from BoT-SORT
    first_seen: float             # Initial detection timestamp
    last_seen: float              # Most recent update timestamp
    first_y: float                # Initial Y position (for movement calc)
    first_x: float                # Initial X position
    first_area: float             # Initial bbox area (for ratio calc)

    # Trajectory history (deque with maxlen=256)
    positions: deque[(x, y, ts)]  # Position samples over time
    bbox_areas: deque[(area, ts)] # Bbox area samples over time

    # Zone tracking
    in_entry_zone: bool           # Currently in entry_zone (Zone A)
    seen_in_zone_a: bool          # Ever seen in Zone A
    seen_in_zone_b: bool          # Ever seen in Zone B
    zone_a_first_ts: float        # First timestamp in Zone A
    zone_b_first_ts: float        # First timestamp in Zone B
    consecutive_zone_b_frames: int  # Sustained Zone B presence
    _zone_b_miss_frames: int      # Jitter tolerance counter
    total_zone_b_frames: int      # Lifetime Zone B frame count

    # Tripwire
    crossed_tripwire: bool        # Ever crossed tripwire in direction

    # Scoring & classification
    direction: str                # entering/exiting/passing/loitering/unknown
    score_total: float            # Current total score
    score_breakdown: dict         # Per-component scores

    # Event flags
    entered_logged: bool          # Entry event already emitted
    exited_logged: bool           # Exit event already emitted
    passing_logged: bool          # Passing event already emitted

    # Visual feedback
    flash_until: float            # Timestamp to flash green on entry
    last_bbox: (x1,y1,x2,y2)     # Most recent bbox
    last_confidence: float        # Most recent detection confidence
```

### 8.2 Track Lifecycle

**1. Track Initialization** (entry_analyzer.py:363):
```python
if person_id not in person_tracks:
    state = PersonTrackState(
        person_id=person_id,
        first_seen=now_ts,
        first_y=cy,
        first_x=cx,
        first_area=bbox_area
    )
    person_tracks[person_id] = state
```

**2. Per-Frame Update** (entry_analyzer.py:380):
```python
# Update last_seen, positions, bbox_areas
state.last_seen = now_ts
state.positions.append((cx, cy, now_ts))
state.bbox_areas.append((bbox_area, now_ts))

# Check zone membership
in_zone_a = sv_zone_a.trigger([detection])
in_zone_b = sv_zone_b.trigger([detection])

# Update zone flags with temporal ordering
if in_zone_a and not state.seen_in_zone_a:
    state.seen_in_zone_a = True
    state.zone_a_first_ts = now_ts

if in_zone_b and not state.seen_in_zone_b:
    state.seen_in_zone_b = True
    state.zone_b_first_ts = now_ts
```

**3. Score Computation** (every frame):
```python
score_total, score_breakdown, metrics = _compute_scores(state, now_ts)
state.score_total = score_total
state.score_breakdown = score_breakdown
```

**4. Classification** (every frame):
```python
new_direction = _classify_state(state, score, metrics)
if new_direction != state.direction:
    state.direction = new_direction
    if new_direction == "entering" and not state.entered_logged:
        emit_entry_event(state)
        state.entered_logged = True
        state.flash_until = now_ts + 1.0  # Flash green for 1 sec
```

**5. Track Cleanup** (entry_analyzer.py:549):
```python
# Remove stale tracks
timeout = PERSON_TIMEOUT  # Default 5 seconds
stale_ids = [
    pid for pid, state in person_tracks.items()
    if now_ts - state.last_seen > timeout
]
for pid in stale_ids:
    del person_tracks[pid]
```

### 8.3 Anti-Duplication Mechanisms

#### 8.3.1 Per-Person Cooldown

**Problem**: Same person re-entering within seconds should not be double-counted

**Solution**: Track entered person IDs with cooldown expiry

```python
# On entry event
if not _id_in_cooldown(person_id, _entered_ids, now_ts):
    _entered_ids[person_id] = now_ts
    emit_entry_event()
else:
    # Skip, person already counted recently
```

**Cooldown Period**: 30 seconds (reuses `WEBHOOK_COOLDOWN_PERSON` setting)

**Expiry Logic**:
```python
def _id_in_cooldown(person_id, id_map, now_ts):
    ts = id_map.get(person_id)
    if ts is None:
        return False
    if now_ts - ts > cooldown_period:
        del id_map[person_id]  # Expire
        return False
    return True
```

#### 8.3.2 Zone B Jitter Tolerance

**Problem**: Person at Zone A/B boundary may flicker in/out of Zone B due to:
- Camera jitter
- Slight body sway
- Detection box instability

**Solution**: Allow 2 frames of Zone B miss before resetting `consecutive_zone_b_frames`

```python
if in_zone_b:
    state.consecutive_zone_b_frames += 1
    state._zone_b_miss_frames = 0
else:
    state._zone_b_miss_frames += 1
    if state._zone_b_miss_frames > 2:
        state.consecutive_zone_b_frames = 0  # Reset after 2 misses
```

**Effect**: Person can briefly leave Zone B (e.g., one foot out) without losing consecutive count

#### 8.3.3 Daily Counter Reset

**Problem**: Entry counter should reset at midnight for daily reports

**Solution**: Check date change on every update

```python
def _rotate_daily_counter_if_needed():
    today = datetime.now(timezone.utc).date()
    if today != _last_entry_day:
        total_entries_today = 0
        _last_entry_day = today
        _entered_ids.clear()  # Also clear cooldown IDs
```

**Timezone**: UTC (can be changed if needed)

### 8.4 Track Memory Management

**Limits**:
- `MAX_TRACKED_PERSONS = 50` (hard limit, oldest tracks evicted)
- `PERSON_TIMEOUT = 5` seconds (automatic cleanup of disappeared tracks)
- `TRAJECTORY_HISTORY_SECONDS = 5` (position/bbox history trimmed)
- Position deque: maxlen=256 samples
- Bbox area deque: maxlen=256 samples

**Cleanup Strategies**:
1. **Timeout-based**: Remove tracks not seen for 5 seconds
2. **Count-based**: If active tracks > MAX_TRACKED_PERSONS, remove oldest
3. **History trimming**: Remove position/bbox samples older than 5 seconds

---

## 9. Zone Calibration

### 9.1 Why Calibration Is Critical

Detection accuracy depends on:
- **Entry zone size**: Too large = false positives from passers-by; too small = missed entries
- **Zone orientation**: Must match actual foot traffic direction
- **Tripwire position**: Supplementary signal for entry detection

**Calibration must be done per camera installation** due to:
- Varying camera angles (ceiling mount, wall mount, angled)
- Different entrance layouts (narrow corridor, wide lobby)
- Lighting conditions affecting detection range

### 9.2 CalibrationData Model

**File**: `calibration.json` (created on first run with defaults)

```json
{
  "entry_zone": {
    "x1": 384,
    "y1": 144,
    "x2": 896,
    "y2": 684
  },
  "tripwire": {
    "x1": 384,
    "y1": 288,
    "x2": 896,
    "y2": 288
  },
  "entry_direction": "top_to_bottom",
  "frame_width": 1280,
  "frame_height": 720,
  "calibrated_at": "2026-02-10T14:30:00.000Z"
}
```

**Fields**:
- `entry_zone`: Rectangle (x1, y1) to (x2, y2) defining Zone A
- `tripwire`: Line from (x1, y1) to (x2, y2)
- `entry_direction`: One of `top_to_bottom`, `bottom_to_top`, `left_to_right`, `right_to_left`
- `frame_width`, `frame_height`: Resolution at calibration time
- `calibrated_at`: ISO 8601 timestamp

### 9.3 Interactive Calibration Tool

**Launch**:
```bash
python main.py --calibrate
```

**Interface** (OpenCV window):
```
┌─────────────────────────────────────────────┐
│         Live camera feed with overlay       │
│                                             │
│   ┌───────────────────────────┐             │
│   │  Entry Zone (green box)   │             │
│   │                           │             │
│   │  ══════════════════════   │  ← Tripwire │
│   │                           │             │
│   └───────────────────────────┘             │
│                                             │
│  Mode: zone                                 │
│  Direction: top_to_bottom                   │
│  Keys: [z]=zone [t]=tripwire [d]=direction  │
│        [s]=save [r]=reset [q]=quit          │
└─────────────────────────────────────────────┘
```

**Workflow**:
1. **Press `z`**: Enter zone drawing mode
   - Click and drag to draw entry zone rectangle
   - Zone should cover the entrance area where people approach

2. **Press `t`**: Enter tripwire drawing mode
   - Click two points to define tripwire line
   - Line should cross the entrance threshold

3. **Press `d`**: Cycle entry direction
   - Toggles: top_to_bottom → bottom_to_top → left_to_right → right_to_left
   - Choose direction matching typical foot traffic

4. **Press `s`**: Save calibration to `calibration.json`

5. **Press `r`**: Reset to defaults (for starting over)

6. **Press `q`**: Quit calibration tool

**Guidelines**:
- Entry zone should be 30-70% of frame width/height
- Zone should cover approach area BEFORE entrance (not just the doorway)
- Tripwire should be near the entrance threshold (door plane)
- Test with `--show-window --debug-boxes` to verify detection

**Implementation**: `calibration/calibration_tool.py`

### 9.4 Web-Based Calibration API

**Alternative to interactive tool**: Calibrate via dashboard

**Endpoints**:
- `GET /calibrate`: HTML calibration interface
- `GET /api/calibration`: Fetch current calibration JSON
- `POST /api/calibration`: Update calibration

**POST Body**:
```json
{
  "entry_zone": {"x1": 400, "y1": 150, "x2": 900, "y2": 700},
  "tripwire": {"x1": 400, "y1": 300, "x2": 900, "y2": 300},
  "entry_direction": "top_to_bottom"
}
```

**Example**:
```bash
curl -X POST http://localhost:8080/api/calibration \
  -H "Content-Type: application/json" \
  -d '{"entry_zone": {...}, "tripwire": {...}, "entry_direction": "top_to_bottom"}'
```

**Live Update**: Analyzer rebuilds zones immediately on calibration change

---

## 10. Dashboard & Monitoring

### 10.1 Dashboard Architecture

**Technology**: FastAPI + Uvicorn (async Python web framework)
**Port**: 8080 (default, configurable via `DASHBOARD_PORT`)
**Threading**: Runs on background thread to avoid blocking detection loop

**Launch**:
```bash
python main.py  # Dashboard starts automatically
# Access at http://localhost:8080
```

**Disable Dashboard**:
```bash
python main.py --no-dashboard
```

### 10.2 Available Endpoints

#### 10.2.1 Main Dashboard

**GET /** - HTML dashboard page

**Features**:
- Live MJPEG video feed with zone overlays
- Real-time metrics (FPS, people count, entries today)
- Event log (last 100 events)
- Tracked people table with scores
- Webhook status indicator
- Uptime counter

**Template**: `dashboard/templates/dashboard.html` (Jinja2)

#### 10.2.2 Video Feed

**GET /video_feed** - MJPEG stream

**Format**: Multipart HTTP stream with JPEG frames

**Usage**:
```html
<img src="http://localhost:8080/video_feed" />
```

**Frame Rate**: ~15 FPS (throttled to avoid overwhelming browser)

**Annotations**:
- Zone A (green box with translucent overlay)
- Zone B (orange box with translucent overlay)
- Tripwire (green/red line)
- Person bounding boxes (color-coded by state)
- Trajectory arrows
- Score overlays (if `--debug-boxes` enabled)

#### 10.2.3 Real-Time Metrics WebSocket

**WebSocket /ws** - Live metrics stream

**Message Format** (JSON, sent every 500ms):
```json
{
  "fps": 25.3,
  "current_people": 2,
  "entries_today": 47,
  "last_entry_time": "2026-02-10T14:32:15.123Z",
  "uptime_seconds": 3847.2,
  "camera_connected": true,
  "webhook_status": {
    "last_success": "HTTP 200",
    "last_failure": null,
    "last_error": null
  },
  "tracked_people": [
    {
      "person_id": 42,
      "bbox": [450, 200, 550, 450],
      "direction": "entering",
      "score": 0.73,
      "confidence": 0.91
    }
  ],
  "event_log": [
    {
      "event": "person_entered",
      "timestamp": "2026-02-10T14:32:15.123Z",
      "person_id": 42,
      "confidence": 0.73,
      "queued": true
    }
  ]
}
```

**Usage** (JavaScript):
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateDashboard(data);
};
```

#### 10.2.4 State Snapshot API

**GET /api/state** - Current system state (JSON)

**Response**: Same structure as WebSocket message (one-time fetch)

**Usage**:
```bash
curl http://localhost:8080/api/state | jq .
```

#### 10.2.5 Calibration API

**GET /api/calibration** - Fetch calibration

**Response**:
```json
{
  "entry_zone": {"x1": 384, "y1": 144, "x2": 896, "y2": 684},
  "tripwire": {"x1": 384, "y1": 288, "x2": 896, "y2": 288},
  "entry_direction": "top_to_bottom",
  "frame_width": 1280,
  "frame_height": 720,
  "calibrated_at": "2026-02-10T14:30:00.000Z"
}
```

**POST /api/calibration** - Update calibration

**Body**: Same as GET response

**Effect**: Updates `calibration.json` and reloads analyzer zones

#### 10.2.6 Test Webhook

**POST /api/test-webhook** - Fire test webhook

**Body**:
```json
{
  "person_id": 999,
  "confidence": 0.85
}
```

**Purpose**: Test webhook endpoint without waiting for real entry

### 10.3 Visual Overlay Guide

**Color Coding** (bounding boxes):

| State      | Color         | Label      | Description                          |
|------------|---------------|------------|--------------------------------------|
| Entering   | Green (flash) | ENTERING   | Entry detected, score ≥ threshold    |
| Entering   | Light green   | ENTERING   | After 1-second flash                 |
| Analyzing  | Yellow        | ANALYZING  | In entry zone, score building        |
| Tracking   | Orange        | TRACKING   | Detected but not in entry zone       |
| Passing    | Gray          | PASSING    | Classified as passing by             |
| Exiting    | Blue          | EXITING    | Classified as exit                   |

**Zone Overlays**:
- Zone A: Green translucent rectangle (15% opacity)
- Zone B: Orange translucent polygon (20% opacity)
- Tripwire: Green line (red when crossed)

**Trajectory Arrows**:
- Drawn from first position to current position
- Color matches person state
- Tip length = 30% of arrow length

**Debug Mode** (`--debug-boxes`):
- Raw YOLO boxes in purple with track ID
- Score breakdown overlay below bbox
- Entry threshold and direction info in HUD

**HUD Overlays**:
```
Entries today: 47
People in frame: 3 | Raw det: 5 | FPS: 25.3
Dir: top_to_bottom | EntryThr: 0.50 | Need ZoneA→ZoneB or TW:1  (debug mode)
```

---

## 11. Webhook System

### 11.1 Webhook Architecture

**Technology**: Async HTTP delivery with httpx
**Threading**: Internal asyncio event loop on background thread
**Queue**: Async queue with cooldown-gated submission

**Lifecycle**:
1. Main thread: Submit webhook job (thread-safe)
2. Background thread: Dequeue job, wait for cooldown slot
3. Async worker: Send HTTP POST with retries
4. On failure: Persist to `webhook_failed_events.jsonl`

### 11.2 Webhook Payload Format

**Endpoint**: Configured via `WEBHOOK_URL` env var

**HTTP Method**: POST

**Headers**:
```
Content-Type: application/json
X-Signature: sha256=<hmac_hex>  (if WEBHOOK_SECRET set)
```

**Body**:
```json
{
  "event": "person_entered",
  "timestamp": "2026-02-10T14:32:15.123456+00:00",
  "confidence": 0.73,
  "person_id": 42,
  "detection_details": {
    "bbox": [450, 200, 550, 450],
    "score_breakdown": {
      "bbox_size": 0.25,
      "y_movement": 0.18,
      "dwell_time": 0.1,
      "tripwire": 0.1,
      "zone_cross": 0.25,
      "velocity": 0.08
    },
    "metrics": {
      "bbox_growth_ratio": 1.28,
      "y_movement_pixels": 45.2,
      "dwell_time_seconds": 2.3,
      "velocity_consistency": 0.76,
      "track_age": 2.8
    }
  },
  "snapshot": "<base64_jpeg_string>",  (if WEBHOOK_INCLUDE_SNAPSHOT=True)
  "metadata": {
    "camera_id": "clinic_entrance_01",
    "frame_number": 1847,
    "total_entries_today": 47
  }
}
```

**Field Descriptions**:
- `event`: Always `"person_entered"` for entry events
- `timestamp`: ISO 8601 timestamp with microsecond precision
- `confidence`: Entry score (0.0-1.0)
- `person_id`: Persistent track ID from BoT-SORT
- `detection_details.bbox`: Bounding box [x1, y1, x2, y2]
- `detection_details.score_breakdown`: Per-component scores
- `detection_details.metrics`: Raw metrics used in scoring
- `snapshot`: Base64-encoded JPEG (640px width, 70% quality) with green bbox highlight
- `metadata.camera_id`: Configurable camera identifier
- `metadata.frame_number`: Frame index since start
- `metadata.total_entries_today`: Daily counter value

### 11.3 HMAC Signature Verification

**When Enabled**: If `WEBHOOK_SECRET` is set (non-empty string)

**Algorithm**: HMAC-SHA256

**Computation**:
```python
secret = "your_webhook_secret"
body = json.dumps(payload).encode("utf-8")
digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
signature = f"sha256={digest}"
# Send as X-Signature header
```

**Verification** (webhook receiver):
```python
import hmac
import hashlib

def verify_signature(body_bytes, signature_header, secret):
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={expected_digest}"
    return hmac.compare_digest(expected_signature, signature_header)

# Usage
is_valid = verify_signature(request.body, request.headers["X-Signature"], secret)
if not is_valid:
    return 403  # Forbidden
```

**Purpose**: Prevents webhook spoofing/tampering

### 11.4 Retry Logic

**Configuration**:
- `WEBHOOK_RETRY_COUNT = 3` (default: 3 retries)
- `WEBHOOK_RETRY_DELAY = 2` (base delay in seconds)
- `WEBHOOK_TIMEOUT = 5` (HTTP request timeout in seconds)

**Retry Strategy**: Exponential backoff

**Example Timeline**:
```
Attempt 1: Immediate
  ↓ (fail, wait 2s)
Attempt 2: +2s
  ↓ (fail, wait 4s)
Attempt 3: +4s
  ↓ (fail, wait 8s)
Attempt 4: +8s (final)
  ↓ (fail, persist to failed_events.jsonl)
```

**Success Criteria**: HTTP status 200-299

**Failure Handling**:
- Network errors (connection refused, timeout) → retry
- HTTP 4xx/5xx → retry (assumes transient server issue)
- After exhausting retries → persist to `webhook_failed_events.jsonl`

**Implementation** (`_send_with_retries` in webhook/sender.py:95):
```python
for attempt in range(retries + 1):
    try:
        response = await client.post(url, content=body, headers=headers)
        if 200 <= response.status_code < 300:
            return True  # Success
    except Exception as exc:
        pass  # Log and retry

    if attempt < retries:
        await asyncio.sleep(base_delay * (2 ** attempt))

persist_failed(job)
return False
```

### 11.5 Cooldown Controls

#### 11.5.1 Per-Person Cooldown

**Setting**: `WEBHOOK_COOLDOWN_PERSON = 30` seconds

**Purpose**: Prevent duplicate webhooks for same person

**Logic**:
```python
last_event_ts = _last_person_event.get(person_id)
if last_event_ts and (now - last_event_ts) < WEBHOOK_COOLDOWN_PERSON:
    return False  # Skip, person in cooldown
_last_person_event[person_id] = now
return True  # Allow
```

**Effect**: Person can re-trigger entry after 30 seconds (e.g., exited and returned)

#### 11.5.2 Global Spacing Cooldown

**Setting**: `WEBHOOK_COOLDOWN_GLOBAL = 3` seconds

**Purpose**: Rate-limit webhook delivery to avoid overwhelming endpoint

**Logic**:
```python
now_monotonic = time.monotonic()
if now_monotonic < _next_global_slot:
    # Delay job submission until next slot
    delay = _next_global_slot - now_monotonic
    await asyncio.sleep(delay)

_next_global_slot = now_monotonic + WEBHOOK_COOLDOWN_GLOBAL
```

**Effect**: Minimum 3 seconds between any two webhooks (even for different people)

### 11.6 Failed Event Persistence

**File**: `webhook_failed_events.jsonl` (JSON Lines format)

**Entry Format**:
```json
{"failed_at": 1707569535.123, "person_id": 42, "payload": {...}}
{"failed_at": 1707569612.456, "person_id": 57, "payload": {...}}
```

**Purpose**: Manual recovery or analysis of lost events

**Recovery Strategy** (manual):
```bash
# Extract failed payloads
cat webhook_failed_events.jsonl | jq .payload > failed_payloads.json

# Replay with curl
cat failed_payloads.json | while read payload; do
  curl -X POST https://your-webhook-url \
    -H "Content-Type: application/json" \
    -d "$payload"
done
```

### 11.7 Webhook Status Monitoring

**Exposed via Dashboard**:
```json
{
  "webhook_status": {
    "last_success": "HTTP 200",
    "last_failure": null,
    "last_error": null
  }
}
```

**Fields**:
- `last_success`: Last successful delivery message (e.g., "HTTP 200")
- `last_failure`: Last failure message (e.g., "HTTP 503: Service Unavailable")
- `last_error`: Last exception message (e.g., "Connection refused")

**Visual Indicator** (dashboard):
- Green: Last event was success
- Red: Last event was failure
- Gray: No events sent yet

---

## 12. Configuration Reference

### 12.1 Environment Variables (.env file)

**Example `.env` file**:
```bash
# Video Source
VIDEO_SOURCE=webcam
WEBCAM_INDEX=0
# RTSP_URL=rtsp://username:password@192.168.1.100:554/stream
# VIDEO_FILE=test_footage.mp4
FRAME_WIDTH=1280
FRAME_HEIGHT=720
TARGET_FPS=15

# Detection
YOLO_MODEL=yolov8m.pt
YOLO_CONFIDENCE=0.4
YOLO_CLASSES=0
TRACKER=botsort_tuned.yaml
YOLO_IMGSZ=1280

# Entry Detection Thresholds
BBOX_GROWTH_RATIO=1.3
Y_MOVEMENT_THRESHOLD=50
DWELL_TIME_MIN=1.5
DWELL_TIME_MAX=15.0
ENTRY_CONFIDENCE_THRESHOLD=0.5
TRAJECTORY_HISTORY_SECONDS=5

# Webhook
WEBHOOK_URL=https://example.com/webhook
WEBHOOK_TIMEOUT=5
WEBHOOK_RETRY_COUNT=3
WEBHOOK_RETRY_DELAY=2
WEBHOOK_COOLDOWN_PERSON=30
WEBHOOK_COOLDOWN_GLOBAL=3
WEBHOOK_INCLUDE_SNAPSHOT=True
WEBHOOK_SECRET=your_shared_secret_here

# Cleanup
PERSON_TIMEOUT=5
MAX_TRACKED_PERSONS=50
ENTRY_LOG_SIZE=100

# Dashboard
DASHBOARD_PORT=8080
DASHBOARD_HOST=0.0.0.0

# Calibration
CALIBRATION_FILE=calibration.json

# Metadata
CAMERA_ID=clinic_entrance_01
LOG_LEVEL=INFO
```

### 12.2 Settings Table

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| **VIDEO_SOURCE** | str | `webcam` | Video source type: `webcam`, `rtsp`, or `file` |
| **WEBCAM_INDEX** | int | `0` | Webcam device index (0=default camera) |
| **RTSP_URL** | str | `""` | RTSP stream URL (used when VIDEO_SOURCE=rtsp) |
| **VIDEO_FILE** | str | `""` | Video file path (used when VIDEO_SOURCE=file) |
| **FRAME_WIDTH** | int | `1280` | Target frame width (actual may vary by source) |
| **FRAME_HEIGHT** | int | `720` | Target frame height |
| **TARGET_FPS** | int | `15` | Target frame rate (actual may vary by source) |
| **YOLO_MODEL** | str | `yolov8m.pt` | YOLO model path (supports .pt, relative/absolute) |
| **YOLO_CONFIDENCE** | float | `0.4` | Min detection confidence (0.0-1.0) |
| **YOLO_CLASSES** | str | `0` | Comma-separated class IDs (0=person in COCO) |
| **TRACKER** | str | `botsort_tuned.yaml` | Tracker config file (botsort or bytetrack) |
| **YOLO_IMGSZ** | int | `1280` | YOLO inference resolution (640, 1280, etc.) |
| **BBOX_GROWTH_RATIO** | float | `1.3` | Bbox growth threshold for entry (1.3 = 30% growth) |
| **Y_MOVEMENT_THRESHOLD** | int | `50` | Directional movement threshold (pixels) |
| **DWELL_TIME_MIN** | float | `1.5` | Min dwell time for entry (seconds) |
| **DWELL_TIME_MAX** | float | `15.0` | Max dwell time before loitering (seconds) |
| **ENTRY_CONFIDENCE_THRESHOLD** | float | `0.5` | Min score for entry classification (0.0-1.0) |
| **TRAJECTORY_HISTORY_SECONDS** | int | `5` | Position history retention (seconds) |
| **WEBHOOK_URL** | str | `https://example.com/webhook` | Webhook endpoint URL |
| **WEBHOOK_TIMEOUT** | int | `5` | HTTP request timeout (seconds) |
| **WEBHOOK_RETRY_COUNT** | int | `3` | Number of retries on failure |
| **WEBHOOK_RETRY_DELAY** | int | `2` | Base retry delay (seconds, exponential backoff) |
| **WEBHOOK_COOLDOWN_PERSON** | int | `30` | Per-person cooldown (seconds) |
| **WEBHOOK_COOLDOWN_GLOBAL** | int | `3` | Global spacing between webhooks (seconds) |
| **WEBHOOK_INCLUDE_SNAPSHOT** | bool | `True` | Include base64 snapshot in payload |
| **WEBHOOK_SECRET** | str | `""` | Shared secret for HMAC signature (empty=disabled) |
| **PERSON_TIMEOUT** | int | `5` | Track cleanup timeout (seconds) |
| **MAX_TRACKED_PERSONS** | int | `50` | Max concurrent tracks (oldest evicted) |
| **ENTRY_LOG_SIZE** | int | `100` | Event log ring buffer size |
| **DASHBOARD_PORT** | int | `8080` | Dashboard HTTP port |
| **DASHBOARD_HOST** | str | `0.0.0.0` | Dashboard bind address (0.0.0.0=all interfaces) |
| **CALIBRATION_FILE** | str | `calibration.json` | Calibration data file path |
| **CAMERA_ID** | str | `clinic_entrance_01` | Camera identifier (sent in webhook metadata) |
| **LOG_LEVEL** | str | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### 12.3 BoT-SORT Tuned Parameters

**File**: `botsort_tuned.yaml`

| Parameter | Default | Tuned | Effect |
|-----------|---------|-------|--------|
| **tracker_type** | botsort | botsort | Tracker algorithm (botsort or bytetrack) |
| **track_high_thresh** | 0.25 | 0.35 | Min confidence for first-stage matching (higher=stricter) |
| **track_low_thresh** | 0.1 | 0.15 | Min confidence for second-stage matching |
| **new_track_thresh** | 0.25 | 0.4 | Min confidence to start new track (higher=less noise) |
| **track_buffer** | 30 | 45 | Frames to keep lost track before deletion (higher=more occlusion tolerance) |
| **match_thresh** | 0.8 | 0.75 | IoU threshold for matching (lower=more willing to match) |
| **fuse_score** | True | True | Fuse detection confidence with tracking score |
| **gmc_method** | None | sparseOptFlow | Camera motion compensation (None, orb, sparseOptFlow) |
| **proximity_thresh** | 0.5 | 0.5 | Distance threshold for ReID matching |
| **appearance_thresh** | 0.8 | 0.8 | Appearance similarity threshold |
| **with_reid** | False | False | Enable appearance ReID (requires appearance model) |

**Tuning Rationale**:
- **Higher initialization thresholds** reduce false tracks from shadows/reflections
- **Larger track buffer** maintains IDs through brief occlusion (people passing behind poles)
- **Tighter match threshold** reduces ID switches when tracks overlap
- **Camera motion compensation** (sparseOptFlow) improves tracking on handheld/PTZ cameras

---

## 13. Video Source Management

### 13.1 VideoStream Architecture

**Design**: Threaded frame reader to decouple capture from processing

**Benefits**:
- **Non-blocking**: Detection loop never waits for camera I/O
- **Frame drop recovery**: Capture thread continuously reads, main loop gets latest frame
- **Stable FPS**: Processing speed doesn't affect capture rate

**Implementation**: `utils/video_stream.py`

### 13.2 Supported Sources

#### 13.2.1 Webcam

**Configuration**:
```bash
VIDEO_SOURCE=webcam
WEBCAM_INDEX=0  # 0=default, 1=second camera, etc.
```

**Initialization**:
```python
capture = cv2.VideoCapture(WEBCAM_INDEX)
```

**Limitations**:
- Index may vary by OS (macOS vs. Linux vs. Windows)
- Resolution/FPS may be constrained by camera hardware
- Use `v4l2-ctl` (Linux) or Camera Settings (macOS) to verify capabilities

#### 13.2.2 RTSP Stream

**Configuration**:
```bash
VIDEO_SOURCE=rtsp
RTSP_URL=rtsp://username:password@192.168.1.100:554/stream
```

**Common RTSP URLs**:
- Hikvision: `rtsp://admin:password@IP:554/Streaming/Channels/101`
- Dahua: `rtsp://admin:password@IP:554/cam/realmonitor?channel=1&subtype=0`
- Generic: `rtsp://username:password@IP:554/stream`

**Authentication**: Embed credentials in URL (URL-encode special characters)

**Buffering Issues**: RTSP may buffer frames. To reduce latency:
```bash
# Set low frame buffering
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp|buffer_size;1024"
python main.py
```

**Network Reliability**: Use TCP transport for reliability (UDP may drop frames)

#### 13.2.3 Video File

**Configuration**:
```bash
VIDEO_SOURCE=file
VIDEO_FILE=test_footage.mp4
```

**Supported Formats**: MP4, AVI, MOV, MKV (anything OpenCV FFmpeg supports)

**EOF Handling**: Stream detects end-of-file and exits gracefully

**Use Cases**:
- Testing with recorded footage
- Offline dataset processing
- Debugging detection parameters

### 13.3 ThreadedVideoStream Internals

**Lifecycle**:

1. **Start**: `stream.start()`
   - Opens cv2.VideoCapture
   - Sets resolution/FPS hints
   - Spawns background reader thread

2. **Reader Loop** (background thread):
   ```python
   while running:
       ok, frame = capture.read()
       if ok:
           with frame_lock:
               latest_frame = frame
               latest_ts = time.time()
       time.sleep(1.0 / TARGET_FPS)
   ```

3. **Main Loop Read**: `frame, ts, count = stream.read()`
   - Copies latest frame from thread-safe buffer
   - Returns None if no frame available yet

4. **Stop**: `stream.stop()`
   - Signals thread to exit
   - Joins thread (max 1s timeout)
   - Releases cv2.VideoCapture

**Thread Safety**: Uses `threading.Lock` to protect frame buffer

---

## 14. Training & Fine-Tuning

### 14.1 Why Fine-Tune?

Pretrained YOLOv8m works well for general person detection, but fine-tuning improves:
- **Small person detection** at distance from camera
- **Occlusion handling** (people partially behind doors/furniture)
- **Domain-specific appearance** (uniforms, clinic equipment)
- **Lighting conditions** (dim lobbies, backlit entrances)

**Expected Improvement**: 5-15% mAP increase after 20-40 epochs with 200+ annotated samples

### 14.2 Dataset Collection Mode

**Launch**:
```bash
python main.py --collect-data \
  --dataset-dir datasets/clinic_person \
  --collect-conf 0.35 \
  --val-every 5
```

**Interface** (OpenCV window):
```
┌─────────────────────────────────────────────┐
│         Live camera feed                    │
│                                             │
│   ┌─────┐  ← Purple box (YOLO proposal)    │
│   │     │                                   │
│   └─────┘                                   │
│                                             │
│   ┌─────┐  ← Green box (your annotation)   │
│   │     │                                   │
│   └─────┘                                   │
│                                             │
│  Samples: 15 train, 3 val                   │
│  Keys: [click/drag]=annotate [right-click]= │
│        remove [space]=save [q]=quit         │
└─────────────────────────────────────────────┘
```

**Workflow**:
1. **Automatic proposals**: YOLO runs at confidence=0.35, draws purple boxes
2. **Manual annotation**: Click-drag to draw green boxes around people
   - Draws tight bounding box (not segmentation)
   - Multiple boxes per frame supported
3. **Auto-copy**: If you don't draw any boxes, YOLO proposals are used
4. **Remove annotation**: Right-click near a box to delete
5. **Save frame**: Press space to save annotated frame
   - Saved to `images/train/` or `images/val/` (every 5th frame to val by default)
   - Labels saved to `labels/train/` or `labels/val/` in YOLO format
6. **Quit**: Press Q

**YOLO Label Format** (`labels/train/sample_001.txt`):
```
0 0.5234 0.6123 0.1234 0.2345
0 0.7123 0.4567 0.0987 0.1567
```
Format: `class x_center y_center width height` (normalized 0-1)

**Dataset Structure** (created automatically):
```
datasets/clinic_person/
├── images/
│   ├── train/
│   │   ├── sample_001.jpg
│   │   ├── sample_002.jpg
│   │   └── ...
│   └── val/
│       ├── sample_006.jpg
│       └── ...
├── labels/
│   ├── train/
│   │   ├── sample_001.txt
│   │   └── ...
│   └── val/
│       └── ...
└── dataset.yaml  (generated at training time)
```

**Collection Tips**:
- Aim for 200+ train samples, 40+ val samples
- Collect diverse scenarios: crowded, single person, occlusion, lighting variations
- Label partial bodies (e.g., person half behind door) to teach occlusion handling
- Reject blurry frames (motion blur) to avoid teaching detector to accept poor quality

### 14.3 Training Mode

**Launch**:
```bash
python main.py --train-model \
  --dataset-dir datasets/clinic_person \
  --train-epochs 40 \
  --train-imgsz 640 \
  --train-batch 16 \
  --train-device cpu \
  --train-name clinic_person_finetune
```

**Validation**:
- Checks dataset has ≥20 train images, ≥5 val images
- Generates `dataset.yaml` with paths and class names

**Training Command** (executed internally):
```python
model = YOLO("yolov8m.pt")
results = model.train(
    data="datasets/clinic_person/dataset.yaml",
    epochs=40,
    imgsz=640,
    batch=16,
    device="cpu",  # or "0" for GPU, "mps" for Mac M1/M2
    name="clinic_person_finetune",
    patience=10,  # Early stopping (epochs / 4)
    save=True,
    plots=True
)
```

**Output**:
```
runs/detect/clinic_person_finetune/
├── weights/
│   ├── best.pt        ← Use this for detection
│   └── last.pt
├── results.png
├── confusion_matrix.png
└── ...
```

**Training Duration**:
- CPU (M1/M2 Mac): ~10-30 sec/epoch (40 epochs = 20-30 min)
- GPU (NVIDIA RTX 3060): ~2-5 sec/epoch (40 epochs = 3-5 min)

### 14.4 Using Fine-Tuned Model

**Update .env**:
```bash
YOLO_MODEL=runs/detect/clinic_person_finetune/weights/best.pt
```

**Or override at runtime**:
```bash
YOLO_MODEL=runs/detect/clinic_person_finetune/weights/best.pt \
python main.py --show-window --debug-boxes
```

**Verification**:
- Check dashboard for improved detection at distance
- Monitor `--debug-boxes` to see confidence scores (should increase for distant people)
- Compare entry counts with original model on same footage

**Recommended Retraining Schedule**:
- Initial deployment: Collect 200 samples, train once
- After 1 week: Collect 50 edge-case samples (failures), retrain
- Monthly: Collect seasonal samples (winter coats, summer attire), retrain

---

## 15. File & Module Reference

### 15.1 Core Files

#### **main.py** (486 lines)

**Purpose**: Application entry point and main detection loop

**Key Functions**:
- `parse_args()`: CLI argument parsing (--calibrate, --collect-data, --train-model, --source, --show-window, --debug-boxes)
- `run()`: Main execution flow
  - Initializes VideoStream, PersonTracker, EntryAnalyzer, WebhookSender, DashboardServer
  - Main loop: frame read → track → analyze → webhook → visualize
  - Signal handling for graceful shutdown (SIGINT/SIGTERM)
- `draw_overlays()`: Zone/person/trajectory visualization
- `build_webhook_payload()`: Constructs webhook JSON with snapshot

**Dependencies**: All other modules

**Entry Point**: `if __name__ == "__main__": sys.exit(run())`

#### **config.py** (197 lines)

**Purpose**: Configuration management with .env file loading

**Key Classes**:
- `Settings`: Dataclass with ALL configurable parameters (53 fields)
- Helper functions: `_env_bool()`, `_env_int()`, `_env_float()`, `_env_str()`

**Loading**: `load_settings()` reads from `.env` file (or env vars), returns Settings instance

**Usage**:
```python
from config import load_settings
settings = load_settings()
print(settings.YOLO_MODEL)
```

### 15.2 Detector Module

#### **detector/person_tracker.py** (98 lines)

**Purpose**: YOLOv8 + BoT-SORT wrapper

**Key Classes**:
- `TrackedPerson`: Dataclass for detection output (person_id, bbox, confidence, center_bottom, frame_number, timestamp)
- `PersonTracker`: Main class
  - `__init__()`: Loads YOLO model
  - `track(frame, frame_number, timestamp)`: Returns List[TrackedPerson]

**Dependencies**: ultralytics (YOLO), numpy

#### **detector/entry_analyzer.py** (615 lines)

**Purpose**: Dual-zone entry/exit detection with graduated scoring

**Key Classes**:
- `EntryEvent`: Dataclass for emitted events (event, timestamp, confidence, person_id, bbox, detection_details)
- `PersonTrackState`: Per-person state (39 fields including trajectory, zones, scoring)
- `EntryAnalyzer`: Main analysis engine
  - `__init__()`: Loads calibration, builds zones
  - `update(detections, now_ts, frame_number)`: Returns List[EntryEvent]
  - `_compute_scores(state, now_ts)`: Graduated scoring logic
  - `_classify_state(state, score, metrics)`: Entry/exit/passing/loitering classification

**Key Functions**:
- `_build_zones(calibration)`: Constructs Zone A and Zone B polygons from calibration
- `_tripwire_crossed_in_direction()`: Line-segment crossing test
- `_velocity_consistency()`: Movement direction consistency check

**Dependencies**: numpy, supervision (PolygonZone)

#### **detector/zone_config.py** (148 lines)

**Purpose**: Calibration data models and persistence

**Key Classes**:
- `EntryZone`: Rectangle (x1, y1, x2, y2) with `normalized()` and `contains()` methods
- `Tripwire`: Line (x1, y1, x2, y2)
- `CalibrationData`: Full calibration (entry_zone, tripwire, entry_direction, frame_width, frame_height, calibrated_at)
- `ZoneConfigManager`: Loads/saves `calibration.json`

**Methods**:
- `load()`: Reads from file, returns CalibrationData (creates default if missing)
- `save(calibration)`: Writes to file with timestamp update
- `update(**kwargs)`: Partial update of calibration fields

### 15.3 Webhook Module

#### **webhook/sender.py** (217 lines)

**Purpose**: Async webhook delivery with retry and cooldown logic

**Key Classes**:
- `WebhookJob`: Dataclass (payload, person_id, not_before_monotonic)
- `WebhookSender`: Main sender
  - `start()`: Spawns background thread with asyncio loop
  - `stop()`: Graceful shutdown with queue flush
  - `submit(payload, person_id)`: Thread-safe job submission with cooldown checks
  - `status()`: Returns last_success, last_failure, last_error

**Internal Methods**:
- `_send_once(payload)`: Single HTTP POST with HMAC signature
- `_send_with_retries(job)`: Exponential backoff retry loop
- `_persist_failed(job)`: Append to webhook_failed_events.jsonl
- `_worker()`: Async queue consumer

**Dependencies**: httpx (async HTTP), asyncio

### 15.4 Dashboard Module

#### **dashboard/web.py** (271 lines)

**Purpose**: FastAPI web dashboard with live feed and metrics

**Key Classes**:
- `DashboardState`: Thread-safe state holder (frame_jpeg, metrics, event_log, calibration)
- `DashboardServer`: Threaded Uvicorn runner
- `create_dashboard_app()`: Factory function returning FastAPI app

**Endpoints**:
- `GET /`: HTML dashboard page
- `GET /calibrate`: Calibration UI page
- `GET /video_feed`: MJPEG stream generator
- `WebSocket /ws`: Real-time metrics stream (500ms interval)
- `GET /api/state`: JSON state snapshot
- `GET /api/calibration`: Fetch calibration
- `POST /api/calibration`: Update calibration
- `POST /api/test-webhook`: Fire test webhook

**Dependencies**: FastAPI, Uvicorn, Jinja2, cv2

### 15.5 Utils Module

#### **utils/video_stream.py** (107 lines)

**Purpose**: Threaded video capture for webcam/RTSP/file

**Key Classes**:
- `VideoSourceConfig`: Dataclass (source_type, webcam_index, rtsp_url, video_file, frame_width, frame_height, target_fps)
- `VideoStream`: Threaded reader
  - `start()`: Opens capture, spawns reader thread
  - `read()`: Returns (frame, timestamp, frame_counter) with thread-safe copy
  - `stop()`: Graceful shutdown
  - `eof` property: True if video file ended

**Dependencies**: cv2, threading

#### **utils/logger.py** (40 lines)

**Purpose**: JSON structured logging

**Key Classes**:
- `JsonFormatter`: Custom logging.Formatter that outputs JSON
- `setup_logger(name, level)`: Returns configured logger

**Output Format**:
```json
{"timestamp": "2026-02-10T14:32:15.123Z", "level": "INFO", "logger": "clinic_detector", "message": "Entry detected", "extra": {"person_id": 42}}
```

**Dependencies**: logging, json

#### **utils/snapshot.py** (41 lines)

**Purpose**: Base64 JPEG encoder for webhook snapshots

**Key Functions**:
- `encode_snapshot_base64(frame, bbox, target_width, jpeg_quality)`: Returns base64 string
  - Overlays green bbox on frame
  - Resizes to target_width (aspect-ratio preserved)
  - Encodes as JPEG with quality setting
  - Returns base64-encoded bytes

**Dependencies**: cv2, numpy, base64

### 15.6 Calibration Module

#### **calibration/calibration_tool.py** (164 lines)

**Purpose**: Interactive OpenCV calibration UI

**Key Classes**:
- `_MouseState`: Internal state for mouse drag tracking
- `CalibrationTool`: Main calibration interface
  - `run()`: Main event loop (read frame → overlay → handle keys → display)
  - `_on_mouse()`: Mouse callback for zone/tripwire drawing
  - `_cycle_direction()`: Cycles through top_to_bottom/bottom_to_top/left_to_right/right_to_left
  - `_draw_overlay()`: Renders current calibration on frame

**Key Bindings**:
- `z`: Zone drawing mode
- `t`: Tripwire drawing mode
- `d`: Cycle entry direction
- `s`: Save calibration
- `r`: Reset to defaults
- `q`: Quit

**Dependencies**: cv2, detector.zone_config

**Launcher**: `run_calibration(source_config, zone_manager, logger)`

### 15.7 Training Module

#### **training/data_collector.py** (304 lines)

**Purpose**: Interactive dataset collection UI

**Key Classes**:
- `DatasetCollectorConfig`: Dataclass (dataset_dir, model_name, confidence, val_every, image_width, image_height, classes)
- Interactive UI with YOLO proposal boxes (purple) and manual annotation (green)

**Key Functions**:
- `run_collection(config, source_config, logger)`: Main collection loop
  - Runs YOLO at configured confidence
  - Allows click-drag annotation
  - Auto-saves to train/val splits
  - Generates YOLO format labels

**Key Bindings**:
- Click-drag: Draw annotation box
- Right-click: Remove nearest annotation
- Space: Save frame with annotations
- Q: Quit

**Dependencies**: cv2, ultralytics (YOLO)

#### **training/trainer.py** (111 lines)

**Purpose**: YOLO fine-tuning wrapper

**Key Classes**:
- `TrainerConfig`: Dataclass (dataset_dir, base_model, epochs, imgsz, batch, device, name)

**Key Functions**:
- `run_training(config, logger)`: Main training flow
  - Validates dataset (min 20 train, 5 val images)
  - Generates `dataset.yaml`
  - Calls `model.train()` with configured parameters
  - Returns path to `best.pt`

**Dependencies**: ultralytics (YOLO), pathlib

### 15.8 Configuration Files

#### **botsort_tuned.yaml** (20 lines)

**Purpose**: Tuned BoT-SORT tracker parameters

**Format**: YAML config file loaded by ultralytics

**Key Tunings**:
- Higher thresholds (0.35 vs 0.25) for stricter tracking
- Larger buffer (45 vs 30) for occlusion tolerance
- Camera motion compensation (sparseOptFlow)

---

## 16. Installation & Setup

### 16.1 System Requirements

**Hardware**:
- CPU: x86_64 or ARM64 (Mac M1/M2 supported)
- RAM: 4GB minimum, 8GB recommended
- Disk: 2GB for dependencies + models
- GPU: Optional (NVIDIA CUDA or Mac Metal acceleration)

**Operating Systems**:
- Linux (Ubuntu 20.04+, Debian 11+)
- macOS 12+ (Monterey or later)
- Windows 10/11 (with Python 3.9+)

**Python Version**: 3.9, 3.10, or 3.11 (3.12 may have dependency issues)

### 16.2 Installation Steps

**1. Clone Repository**:
```bash
git clone https://github.com/your-org/clinic-entrance-detector.git
cd clinic-entrance-detector
```

**2. Create Virtual Environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

**3. Install Dependencies**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Key Dependencies** (requirements.txt):
```
ultralytics>=8.0.0      # YOLO + tracking
opencv-python>=4.8.0    # Computer vision
supervision>=0.16.0     # PolygonZone utilities
fastapi>=0.104.0        # Web dashboard
uvicorn>=0.24.0         # ASGI server
httpx>=0.25.0           # Async HTTP client
python-dotenv>=1.0.0    # .env file loading
numpy>=1.24.0
jinja2>=3.1.0           # Dashboard templates
```

**4. Download YOLO Model** (optional, auto-downloads on first run):
```bash
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt
```

**5. Configure Environment**:
```bash
cp .env.example .env
nano .env  # Edit VIDEO_SOURCE, WEBHOOK_URL, etc.
```

**6. Run Calibration**:
```bash
python main.py --calibrate
```

**7. Start Detection**:
```bash
python main.py --show-window
```

**8. Access Dashboard**:
```
http://localhost:8080
```

### 16.3 GPU Acceleration (Optional)

**NVIDIA CUDA** (Linux/Windows):
```bash
# Install CUDA 11.8 or 12.1 from NVIDIA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**Mac Metal** (M1/M2):
```bash
# PyTorch with Metal backend (included in recent ultralytics)
# No additional steps needed, MPS auto-detected
```

**Verify GPU**:
```python
import torch
print(torch.cuda.is_available())  # True for NVIDIA
print(torch.backends.mps.is_available())  # True for Mac
```

**Set Device**:
```bash
# .env file
TRAIN_DEVICE=0  # NVIDIA GPU 0
# or
TRAIN_DEVICE=mps  # Mac Metal
```

### 16.4 Docker Deployment (Recommended for Production)

**Dockerfile**:
```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**docker-compose.yml**:
```yaml
version: '3.8'
services:
  clinic-detector:
    build: .
    ports:
      - "8080:8080"
    environment:
      - VIDEO_SOURCE=rtsp
      - RTSP_URL=rtsp://camera:554/stream
      - WEBHOOK_URL=https://your-webhook-endpoint.com
      - LOG_LEVEL=INFO
    volumes:
      - ./calibration.json:/app/calibration.json
      - ./logs:/app/logs
    restart: unless-stopped
```

**Run**:
```bash
docker-compose up -d
docker-compose logs -f clinic-detector
```

---

## 17. CLI Reference

### 17.1 Command-Line Arguments

```bash
python main.py [OPTIONS]
```

### 17.2 Mode Selection

| Flag | Description |
|------|-------------|
| `--calibrate` | Launch interactive calibration tool and exit |
| `--collect-data` | Launch dataset collection mode for fine-tuning |
| `--train-model` | Fine-tune YOLO model using collected dataset |
| (none) | Run detection with webhook delivery (default mode) |

### 17.3 Video Source Options

| Flag | Values | Description |
|------|--------|-------------|
| `--source` | `webcam`, `rtsp`, `file` | Override VIDEO_SOURCE env var |
| `--url` | URL string | Override RTSP_URL env var |
| `--video` | File path | Override VIDEO_FILE env var |

### 17.4 Display & Debugging

| Flag | Description |
|------|-------------|
| `--show-window` | Show local OpenCV preview window (default: off) |
| `--debug-boxes` | Draw raw YOLO boxes + score breakdown overlays |
| `--no-dashboard` | Disable FastAPI web dashboard |

### 17.5 Calibration Options

| Flag | Default | Description |
|------|---------|-------------|
| `--calibration-file` | `calibration.json` | Path to calibration data file |

### 17.6 Dataset Collection Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dataset-dir` | `datasets/clinic_person` | Dataset root directory |
| `--collect-conf` | `0.35` | YOLO proposal confidence threshold |
| `--val-every` | `5` | Save every Nth sample to validation split |

### 17.7 Training Options

| Flag | Default | Description |
|------|---------|-------------|
| `--train-epochs` | `40` | Number of training epochs |
| `--train-imgsz` | `640` | Training image size (640, 1280, etc.) |
| `--train-batch` | `16` | Training batch size |
| `--train-device` | `cpu` | Training device (`cpu`, `0`, `mps`) |
| `--train-name` | `clinic_person_finetune` | Training run name (output folder) |

### 17.8 Logging

| Flag | Values | Description |
|------|--------|-------------|
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Override LOG_LEVEL env var |

### 17.9 Example Commands

**1. Initial Calibration**:
```bash
python main.py --calibrate --source webcam
```

**2. Run Detection with Local Preview**:
```bash
python main.py --show-window --debug-boxes
```

**3. Run Detection with RTSP Camera**:
```bash
python main.py --source rtsp --url rtsp://admin:pass@192.168.1.100:554/stream
```

**4. Collect Training Dataset**:
```bash
python main.py --collect-data --dataset-dir datasets/my_clinic --collect-conf 0.3
```

**5. Train Fine-Tuned Model** (GPU):
```bash
python main.py --train-model \
  --dataset-dir datasets/my_clinic \
  --train-epochs 50 \
  --train-imgsz 1280 \
  --train-batch 8 \
  --train-device 0
```

**6. Run with Fine-Tuned Model**:
```bash
YOLO_MODEL=runs/detect/clinic_person_finetune/weights/best.pt \
python main.py --show-window
```

**7. Test with Video File**:
```bash
python main.py --source file --video test_footage.mp4 --show-window
```

**8. Production Mode** (no window, dashboard only):
```bash
python main.py  # Access dashboard at http://localhost:8080
```

**9. Headless Mode** (no dashboard, webhook only):
```bash
python main.py --no-dashboard
```

---

## 18. Known Limitations & Future Improvements

### 18.1 Current Limitations

#### 18.1.1 Detection Limitations

**1. Crowded Scenes (>10 people)**
- **Issue**: Track ID switches increase when people overlap
- **Impact**: Potential double-counting if same person gets new ID
- **Mitigation**: Per-person cooldown (30s) reduces duplicates
- **Future**: ReID-based tracking with appearance features

**2. Occlusion at Zone B Boundary**
- **Issue**: Person briefly hidden at doorframe may not reach 5 consecutive Zone B frames
- **Mitigation**: Fallback rule uses tripwire + higher score threshold
- **Future**: Probabilistic state estimation (Kalman filter for zone membership)

**3. Children & Wheelchairs**
- **Issue**: Small bboxes may not reach BBOX_GROWTH_RATIO threshold
- **Mitigation**: Lower threshold to 1.15 for pediatric clinics
- **Future**: Multi-class detection (person, wheelchair, stroller)

**4. Camera Motion**
- **Issue**: Handheld/PTZ camera motion causes spurious movement signals
- **Mitigation**: BoT-SORT's sparseOptFlow compensates for global motion
- **Future**: IMU-based motion filtering

#### 18.1.2 Webhook Limitations

**1. No Delivery Guarantee**
- **Issue**: After 3 retries, event is only persisted to JSONL (not redelivered)
- **Mitigation**: Monitor `webhook_failed_events.jsonl` and replay manually
- **Future**: Dead-letter queue with automatic retry schedule

**2. No Batch Delivery**
- **Issue**: Each entry sends separate HTTP request (high volume = many requests)
- **Mitigation**: Global cooldown (3s) provides rate limiting
- **Future**: Batch webhook mode (send N events every M seconds)

**3. No TLS Client Certificates**
- **Issue**: HMAC signature only, no mutual TLS authentication
- **Future**: Support for client cert authentication

#### 18.1.3 Dashboard Limitations

**1. Single Client MJPEG**
- **Issue**: Multiple browsers connecting to `/video_feed` may cause frame drops
- **Mitigation**: Use WebSocket for metrics only, MJPEG for single viewer
- **Future**: HLS/DASH streaming for multi-client support

**2. No Historical Analytics**
- **Issue**: Only shows current metrics + last 100 events
- **Mitigation**: Webhook consumer should persist to database
- **Future**: Built-in time-series database (SQLite) with charts

**3. No User Authentication**
- **Issue**: Dashboard is publicly accessible (anyone on network can view)
- **Mitigation**: Deploy behind reverse proxy with auth (nginx + basic auth)
- **Future**: Built-in user authentication with JWT tokens

#### 18.1.4 Performance Limitations

**1. CPU-Bound on Single Core**
- **Issue**: YOLO inference is single-threaded (Python GIL)
- **Mitigation**: Use GPU for 3-5x speedup
- **Future**: Multi-process pipeline (separate processes for detection, tracking, analysis)

**2. High Memory Usage with Many Tracks**
- **Issue**: 256-sample position history per person (50 people = 12,800 samples)
- **Mitigation**: MAX_TRACKED_PERSONS=50 limit, TRAJECTORY_HISTORY_SECONDS=5 trimming
- **Future**: Sparse trajectory storage (only keypoints)

### 18.2 Future Enhancements

#### 18.2.1 Detection Enhancements

**1. Multi-Camera Fusion**
- **Approach**: Homography-based ground-plane mapping, track ID association across views
- **Benefit**: Eliminates blind spots, improves accuracy

**2. Pose Estimation**
- **Approach**: Add YOLOv8 pose model for keypoint detection
- **Benefit**: Distinguish entering (facing door) from exiting (facing away) by body orientation

**3. Re-Identification (ReID)**
- **Approach**: Enable BoT-SORT's ReID with appearance model (OSNet, FastReID)
- **Benefit**: Maintain track IDs through long occlusion (5-10 seconds)

**4. Adaptive Thresholds**
- **Approach**: Auto-tune ENTRY_CONFIDENCE_THRESHOLD based on historical FP/FN rates
- **Benefit**: Reduces manual tuning per installation

#### 18.2.2 Webhook Enhancements

**1. Dead-Letter Queue**
- **Implementation**: SQLite table for failed events with retry scheduler
- **Benefit**: Zero event loss even if webhook endpoint is down for hours

**2. Batch Delivery**
- **Implementation**: Accumulate events in 10-second window, send as JSON array
- **Benefit**: Reduces HTTP overhead for high-traffic clinics

**3. Multi-Endpoint Support**
- **Implementation**: Allow multiple webhook URLs with per-URL retry configs
- **Benefit**: Send to both analytics system and access control system

#### 18.2.3 Dashboard Enhancements

**1. Historical Charts**
- **Implementation**: Store entry counts in SQLite, render with Chart.js
- **Benefit**: Visualize peak hours, weekly trends

**2. Alerts & Notifications**
- **Implementation**: Email/SMS alerts when entries > threshold or system errors
- **Benefit**: Proactive monitoring

**3. Calibration Presets**
- **Implementation**: Store multiple calibration profiles (day/night, summer/winter)
- **Benefit**: Quick switching without recalibration

#### 18.2.4 Deployment Enhancements

**1. Kubernetes Helm Chart**
- **Implementation**: Packaged Helm chart with ConfigMaps, Secrets, PVCs
- **Benefit**: Enterprise-grade deployment with auto-scaling

**2. Edge Deployment (NVIDIA Jetson)**
- **Implementation**: TensorRT-optimized YOLO model for Jetson Nano/Xavier
- **Benefit**: Embedded deployment at camera edge (no server needed)

**3. Cloud Integration (AWS/Azure)**
- **Implementation**: S3/Blob storage for snapshots, Lambda/Functions for webhook processing
- **Benefit**: Serverless architecture for multi-site deployments

### 18.3 Research Opportunities

**1. Attention Mechanism for Entry Intent**
- **Approach**: Transformer-based model predicting entry probability from trajectory sequence
- **Benefit**: Earlier detection (predict before reaching Zone B)

**2. Federated Learning for Multi-Site Deployment**
- **Approach**: Train models locally, aggregate updates centrally without sharing raw data
- **Benefit**: Improve accuracy across sites while preserving privacy

**3. 3D Pose Estimation for Direction**
- **Approach**: Monocular 3D pose estimation to detect body orientation in 3D space
- **Benefit**: More robust entry/exit distinction

---

## Appendix A: Troubleshooting

### A.1 Common Issues

**Issue: "Failed to open video source"**
- **Cause**: Camera not connected or wrong index/URL
- **Fix**: Check `VIDEO_SOURCE`, `WEBCAM_INDEX`, `RTSP_URL` in .env
- **Verify**: `v4l2-ctl --list-devices` (Linux), `system_profiler SPCameraDataType` (Mac)

**Issue: "No entry detections despite people entering"**
- **Cause**: Miscalibrated entry zone or thresholds too strict
- **Fix**: Run `--calibrate` to adjust zone, or lower `ENTRY_CONFIDENCE_THRESHOLD` to 0.4
- **Debug**: Use `--debug-boxes` to see score breakdown

**Issue: "Duplicate entries for same person"**
- **Cause**: Track ID switch or cooldown too short
- **Fix**: Increase `WEBHOOK_COOLDOWN_PERSON` to 60 seconds
- **Verify**: Check dashboard tracked_people table for ID switches

**Issue: "Webhook timeouts"**
- **Cause**: Endpoint slow or unreachable
- **Fix**: Increase `WEBHOOK_TIMEOUT` to 10 seconds
- **Monitor**: Check `webhook_failed_events.jsonl` for errors

**Issue: "Low FPS (<10)"**
- **Cause**: CPU bottleneck or high resolution
- **Fix**: Reduce `YOLO_IMGSZ` to 640, or enable GPU acceleration
- **Profile**: Add `--log-level DEBUG` to see frame timings

---

## Appendix B: API Reference

See Section 10.2 for full endpoint documentation.

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **BoT-SORT** | Kalman filter-based object tracker with camera motion compensation |
| **Bbox** | Bounding box (rectangular region around detected object) |
| **COCO** | Common Objects in Context dataset (80 classes including person) |
| **Dwell Time** | Duration person spends in entry zone |
| **Entry Direction** | Configured direction of entry (top_to_bottom, bottom_to_top, left_to_right, right_to_left) |
| **Graduated Scoring** | Partial credit scoring system (vs. binary threshold) |
| **HMAC** | Hash-based Message Authentication Code (cryptographic signature) |
| **IoU** | Intersection over Union (overlap metric for bounding boxes) |
| **MJPEG** | Motion JPEG (video stream as sequence of JPEG images) |
| **mAP** | Mean Average Precision (object detection accuracy metric) |
| **ReID** | Re-identification (matching objects across frames using appearance) |
| **RTSP** | Real-Time Streaming Protocol (IP camera streaming standard) |
| **Tripwire** | Virtual line for legacy crossing detection |
| **YOLOv8** | You Only Look Once v8 (real-time object detection model) |
| **Zone A** | Outer approach zone (full entry rectangle) |
| **Zone B** | Inner entrance zone (35% of Zone A near entry threshold) |

---

## Appendix D: References

**Papers**:
- YOLOv8: Ultralytics (2023) - https://github.com/ultralytics/ultralytics
- BoT-SORT: Aharon et al. (2022) - "BoT-SORT: Robust Associations Multi-Pedestrian Tracking"
- ByteTrack: Zhang et al. (2022) - "ByteTrack: Multi-Object Tracking by Associating Every Detection Box"

**Libraries**:
- Ultralytics: https://docs.ultralytics.com
- Supervision: https://supervision.roboflow.com
- FastAPI: https://fastapi.tiangolo.com
- OpenCV: https://docs.opencv.org

**Community**:
- GitHub Issues: https://github.com/your-org/clinic-entrance-detector/issues
- Discussions: https://github.com/your-org/clinic-entrance-detector/discussions

---

**End of Documentation**

*This document is maintained by the development team. For updates, see CHANGELOG.md*

*Last Generated: 2026-02-10 by Claude Code*
