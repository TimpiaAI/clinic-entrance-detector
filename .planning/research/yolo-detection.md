# Clinic Entrance Detection System: Comprehensive Research

**Project:** clinic-entrance-detector
**Researched:** 2026-03-04
**Overall confidence:** HIGH (codebase analysis) / MEDIUM-HIGH (ecosystem recommendations)

---

## Table of Contents

1. [Current System Analysis](#1-current-system-analysis)
2. [YOLO for Entrance/Doorway Detection](#2-yolo-for-entrancedoorway-detection)
3. [Person Counting at Entrances](#3-person-counting-at-entrances)
4. [Zone-Based Detection Patterns](#4-zone-based-detection-patterns)
5. [YOLO Model Selection](#5-yolo-model-selection)
6. [Tracker Comparison for Entrance Monitoring](#6-tracker-comparison-for-entrance-monitoring)
7. [Edge Deployment Optimization](#7-edge-deployment-optimization)
8. [Similar Open-Source Projects](#8-similar-open-source-projects)
9. [False Positive Reduction](#9-false-positive-reduction)
10. [Night/Lighting Challenges](#10-nightlighting-challenges)
11. [Multi-Camera and Depth Sensor Approaches](#11-multi-camera-and-depth-sensor-approaches)
12. [Recommendations Summary](#12-recommendations-summary)

---

## 1. Current System Analysis

**Confidence: HIGH** (direct codebase analysis)

### Architecture Overview

The system is a Python application using:
- **YOLOv8m** (medium) for person detection at **1280px** inference resolution
- **BoT-SORT** (tuned) as the multi-object tracker
- **Dual-zone detection** with Supervision library's PolygonZone
- **Graduated scoring algorithm** for entry classification
- **Webhook delivery** system for external integration (triggers a VLC-based video workflow via Flask)
- **FastAPI dashboard** for real-time monitoring
- **Interactive calibration tool** for zone/tripwire placement

### Detection Pipeline

```
Video Stream (1280x720 @ 15fps)
    |
    v
YOLOv8m (conf=0.4, class=0/person, imgsz=1280)
    |
    v
BoT-SORT Tracker (tuned config)
    |
    v
Entry Analyzer (dual-zone + tripwire + scoring)
    |
    v
Events: person_entered / person_exited / passing
    |
    v
Webhook -> Flask controller (plays VLC videos + Whisper STT)
```

### Dual-Zone Detection Logic

The system splits a calibrated entry zone into two polygonal areas:

- **Zone A (outer):** Full entry zone rectangle -- the approach area
- **Zone B (inner):** 35% portion near the tripwire -- the "committed to entering" area

Entry direction determines which edge gets Zone B:
- `top_to_bottom`: Zone B = bottom 35%
- `bottom_to_top`: Zone B = top 35%
- `left_to_right`: Zone B = right 35%
- `right_to_left`: Zone B = left 35%

**Entry detection requires**: Zone A seen first, THEN Zone B (temporal ordering), with at least 5 consecutive Zone B frames, velocity consistency >= 0.3, and score >= threshold (0.5).

### Scoring Algorithm

The system uses a graduated multi-factor scoring approach (max score ~0.9):

| Factor | Weight | Measurement |
|--------|--------|-------------|
| Bbox growth | 0.0-0.25 | Ratio of current area to first-seen area (approaching = growing) |
| Directional movement | 0.0-0.20 | Pixels moved in entry direction |
| Dwell time | 0.0-0.10 | Time in zone (1.5s-15s sweet spot) |
| Tripwire crossing | 0.0-0.10 | Binary: crossed the legacy tripwire line |
| Zone A-to-B crossing | 0.0-0.25 | Graduated by consecutive Zone B frames (min 5) |
| Velocity consistency | 0.0-0.10 | Fraction of forward steps in last 20 positions |

**Classification rules:**
1. **Primary (dual-zone):** Zone A->B with 5+ consecutive B frames, score >= 0.5, dwell <= 15s, velocity >= 0.3
2. **Fallback (tripwire):** Score >= 0.6, tripwire crossed, dwell <= 15s, track age >= 1s, velocity >= 0.4
3. **Exiting:** Bbox shrinking (ratio <= 0.85) AND reverse movement
4. **Passing:** Short dwell AND minimal movement
5. **Loitering:** Dwell > 15s

### BoT-SORT Tuned Configuration

```yaml
tracker_type: botsort
track_high_thresh: 0.35    # Stricter than default 0.25
track_low_thresh: 0.15     # Higher than default 0.1
new_track_thresh: 0.4      # Higher than default 0.25
track_buffer: 45            # Higher than default 30
match_thresh: 0.75          # Tighter than default 0.8
fuse_score: True
gmc_method: sparseOptFlow   # Camera motion compensation
with_reid: False             # ReID disabled
```

### Current Configuration (.env vs config.py defaults)

Notable discrepancy: `.env` uses `yolov8n.pt` (nano) and `bytetrack.yaml`, while `config.py` defaults to `yolov8m.pt` (medium) and `botsort_tuned.yaml`. The config.py defaults take precedence only when env vars are not set, so the **active model depends on whether .env is loaded**.

### Strengths of Current Implementation

1. **Multi-factor scoring** is more robust than simple line-crossing; reduces false positives
2. **Dual-zone approach** adds temporal validation (must traverse A then B)
3. **Velocity consistency** check prevents static/loitering false triggers
4. **Dwell time bounds** filter out too-fast (passing) and too-slow (loitering) tracks
5. **Per-person cooldown** prevents duplicate webhook triggers
6. **Daily counter rotation** for clean daily stats
7. **Built-in calibration tool** makes deployment per-site easy
8. **Fine-tuning pipeline** (data collection + training) for site-specific optimization

### Weaknesses / Areas for Improvement

1. **Model version:** YOLOv8 is two generations behind current (YOLO26 released Jan 2026)
2. **ReID disabled:** Track ID instability likely; person leaving and re-entering gets new ID
3. **35% zone split is hardcoded:** Not configurable per-deployment
4. **No NMS-free pipeline:** YOLOv8 still uses NMS post-processing
5. **No model export:** Running PyTorch inference directly (no TensorRT/ONNX optimization)
6. **1280px inference on YOLOv8m:** Very expensive for edge; ~234ms per frame on CPU
7. **No handling of lighting changes:** No image preprocessing or adaptation
8. **Single camera only:** No multi-camera fusion
9. **No persistence of track history:** Lost on restart
10. **.env/config.py model mismatch:** Confusing for deployments

---

## 2. YOLO for Entrance/Doorway Detection

**Confidence: MEDIUM-HIGH** (multiple sources agree)

### Specialized Models/Datasets

There are **no YOLO models specifically pre-trained for entrance/doorway detection**. The standard COCO-pretrained person detection (class 0) is the universal starting point. This is appropriate because:

- COCO includes diverse person poses and environments
- Entrance detection is fundamentally person detection + spatial logic
- The spatial/directional logic belongs in the analyzer, not the detector

### Recommended Approach

Use **COCO-pretrained person detection** as the base, then **fine-tune on site-specific data** if needed. The current system's data collection + training pipeline is the right approach.

### Key Research Papers/Projects

- **"Evaluation of several YOLO architecture versions for person detection and counting"** (2025, Multimedia Tools and Applications): Compared YOLOv3-v7 for person counting. Found that later versions significantly outperform earlier ones for crowd scenarios.
- **PyImageSearch "People Tracker with YOLOv12 and Centroid Tracker"** (2025): Demonstrates entrance/exit counting with latest YOLO + simple centroid tracking.
- **Ultralytics built-in ObjectCounter** (YOLO26): Native line-crossing and zone-based counting -- could simplify the implementation significantly.

### Sources

- [Evaluation of YOLO architectures for person detection](https://link.springer.com/article/10.1007/s11042-025-20662-z)
- [People Tracker with YOLOv12 - PyImageSearch](https://pyimagesearch.com/2025/07/14/people-tracker-with-yolov12-and-centroid-tracker/)
- [Ultralytics Object Counting Guide](https://docs.ultralytics.com/guides/object-counting/)

---

## 3. Person Counting at Entrances

**Confidence: HIGH** (well-documented area, multiple verified sources)

### Approach Comparison

| Approach | Accuracy | Complexity | Edge-Friendly | Best For |
|----------|----------|------------|---------------|----------|
| YOLO + Line crossing | Good (90-95%) | Low | Yes | Simple single-door entrances |
| YOLO + Dual zone (current) | Very good (95-98%) | Medium | Yes | Directional validation needed |
| YOLO + Tracker + Re-ID | Excellent (97-99%) | High | Medium | Re-identification needed |
| Ultralytics ObjectCounter | Good (90-95%) | Very low | Yes | Quick deployment |
| Depth sensor (RealSense) | Excellent (98%+) | Medium | Medium | Lighting-invariant needed |
| Thermal + YOLO | Excellent (97%+) | High | No | Extreme lighting variation |

### The Current Dual-Zone Approach is Sound

The system's approach (YOLO detection -> tracker -> dual-zone analysis -> multi-factor scoring) is more sophisticated than most open-source alternatives, which typically use simple line-crossing. The multi-factor scoring with graduated credits is a notable strength.

**However**, the Ultralytics ecosystem now provides built-in `ObjectCounter` and `RegionCounter` solutions that handle much of this logic natively. The current custom implementation offers more control but at higher maintenance cost.

### Supervision Library Integration

The project already uses Supervision's `PolygonZone` for zone containment checks. Supervision also offers `LineZone` with built-in `crossed_in` / `crossed_out` counters that could replace or supplement the tripwire logic:

```python
import supervision as sv
line_zone = sv.LineZone(start=sv.Point(x1, y1), end=sv.Point(x2, y2))
crossed_in, crossed_out = line_zone.trigger(detections=sv_detections)
```

This could simplify the tripwire portion of the scoring while keeping the dual-zone approach.

### Sources

- [Building In-and-Out People Counter with YOLOv8](https://medium.com/@rajith.ravikumar/building-an-in-and-out-people-counter-with-opencv-and-yolov8-87e2b778cc65)
- [Ultralytics Region Counting](https://docs.ultralytics.com/guides/region-counting/)
- [Supervision PolygonZone](http://supervision.roboflow.com/detection/tools/polygon_zone/)

---

## 4. Zone-Based Detection Patterns

**Confidence: HIGH** (verified via official docs and multiple implementations)

### Pattern Comparison

| Pattern | How It Works | Pros | Cons |
|---------|-------------|------|------|
| **Single line crossing** | Track centroid crossing a line | Simple, fast | No direction confidence, jitter-prone |
| **Dual zone (A->B)** | Track must appear in outer zone, then inner | Directional validation, temporal ordering | Requires calibration, zone size matters |
| **Virtual tripwire + dwell** | Line crossing + minimum time in zone | Filters fast pass-throughs | Still jitter-prone on the line |
| **Trajectory analysis** | Analyze full path shape | Most robust, handles complex paths | Most complex, highest latency |

### Current System: Hybrid Approach

The current system uses **all four patterns simultaneously**, which is actually best-in-class:
1. Dual zone (Zone A -> Zone B) as primary
2. Tripwire crossing as fallback/bonus
3. Dwell time as a scoring factor
4. Velocity consistency (simplified trajectory analysis)

### Key Insight: The 35% Zone B Split

The hardcoded 35% split for Zone B may not be optimal for all camera angles and door geometries. Consider:

- **Narrow doors:** Zone B should be smaller (20-25%) to avoid the outer zone being too small
- **Wide lobbies:** Zone B could be larger (40-50%) for more "commitment area"
- **Side-angle cameras:** The split axis may not align with actual movement paths

**Recommendation:** Make the zone B split ratio configurable (currently hardcoded in `entry_analyzer.py` line 99 as `split = 0.35`).

### Production Pattern: Direction-Aware Zone Counting

The most reliable pattern used in production surveillance systems:

1. Define two non-overlapping zones on either side of the entrance
2. Track the order in which a person appears in each zone
3. Zone A then Zone B = entering; Zone B then Zone A = exiting
4. Require minimum consecutive frames in each zone to filter jitter
5. Apply per-ID cooldown to prevent double-counting

This closely matches the current implementation, validating the design choice.

### Sources

- [Felenasoft Cross-Line Detector](https://felenasoft.com/xeoma/en/articles/visitors-counter-cross-line-detector/)
- [Tripwire vs Motion Detection](https://www.grep.sg/2025/07/30/tripwire-vs-motion-detection-which-is-better-for-smart-video-surveillance/)
- [Ultralytics TrackZone](https://docs.ultralytics.com/guides/trackzone/)

---

## 5. YOLO Model Selection

**Confidence: HIGH** (verified via Ultralytics official documentation)

### Model Generation Comparison (as of March 2026)

| Model | mAP@50-95 | CPU Speed | GPU Speed | Params | FLOPs | Status |
|-------|-----------|-----------|-----------|--------|-------|--------|
| YOLOv8n | 37.3 | 80.4ms | 3.2ms | 1.47M | 8.7B | Superseded |
| YOLOv8m | 50.2 | 234.7ms | 25.9ms | 25.9M | 78.9B | Superseded |
| YOLO11n | 39.5 | 56.1ms | 1.5ms | 2.6M | 6.5B | Superseded |
| YOLO11m | 51.5 | 183.2ms | 4.7ms | 20.1M | 68.0B | Superseded |
| **YOLO26n** | **40.9** | **38.9ms** | **1.7ms** | **2.4M** | **5.4B** | **Current** |
| **YOLO26m** | **53.1** | **220.0ms** | **4.7ms** | **20.4M** | **68.2B** | **Current** |
| YOLOv12n | 40.6 | N/A | 1.64ms | N/A | N/A | Attention-based |

*All benchmarks at 640px input on COCO val2017. CPU = ONNX, GPU = T4 TensorRT10.*

### Recommendation: Upgrade to YOLO26

**For the clinic entrance use case, use YOLO26n (nano) instead of YOLOv8m (medium).**

Rationale:
1. **YOLO26n (40.9 mAP) vs YOLOv8n (37.3 mAP):** 10% better accuracy at the nano tier
2. **YOLO26n CPU speed (38.9ms) vs YOLOv8m CPU speed (234.7ms):** 6x faster
3. **YOLO26n is NMS-free:** Deterministic latency, better edge compatibility
4. **Person detection in entrance scenarios is not hard:** Nano is sufficient; people are large, close objects in a controlled environment
5. **The medium model is overkill:** At 1280px inference with YOLOv8m, you are spending ~235ms per frame on CPU for a task that YOLO26n handles in ~39ms

**If higher accuracy is needed**, use YOLO26s (small) as the sweet spot, not medium.

### Alternative: RT-DETR / RF-DETR

RT-DETR achieved 53.1% AP at 108 FPS (T4 GPU), surpassing YOLOv8 in both accuracy and speed. However, for this use case:

- **Not recommended for edge/CPU:** Transformer models are much slower on CPU
- **Only relevant if running on a GPU-equipped system**
- **YOLO26 already incorporates key improvements** from transformer research

### YOLO-NAS

YOLO-NAS showed improvements over YOLOv8 but has been superseded by YOLO11 and YOLO26. Not recommended for new projects.

### Sources

- [YOLO26 vs YOLO11 Comparison - Ultralytics](https://docs.ultralytics.com/compare/yolo26-vs-yolo11/)
- [YOLO11 vs YOLOv8 Comparison - Ultralytics](https://docs.ultralytics.com/compare/yolo11-vs-yolov8/)
- [Best Object Detection Models 2025 - Roboflow](https://blog.roboflow.com/best-object-detection-models/)
- [Ultralytics Models Overview](https://docs.ultralytics.com/models/)

---

## 6. Tracker Comparison for Entrance Monitoring

**Confidence: MEDIUM-HIGH** (verified via official docs + multiple community sources)

### Tracker Comparison Matrix

| Tracker | Speed | ID Stability | Occlusion Handling | ReID Support | Edge-Friendly | Best For |
|---------|-------|-------------|-------------------|--------------|---------------|----------|
| **BoT-SORT** | Medium | Good | Good (GMC) | Optional | Medium | Balanced accuracy/speed |
| **ByteTrack** | Fast | Fair | Fair | No | Yes | Speed-critical, static camera |
| **OC-SORT** | Medium | Good | Excellent | No | Yes | Motion/camera movement |
| **StrongSORT** | Slow | Excellent | Excellent | Yes (deep) | No | Identity preservation |
| **Deep OC-SORT** | Slow | Very good | Good | Yes | No | Re-identification needed |

### For Clinic Entrance: BoT-SORT is the Right Choice

The current BoT-SORT choice is sound for this scenario because:

1. **Short tracking distance:** People traverse a small zone (maybe 2-4 seconds of tracking needed)
2. **Camera motion compensation (GMC):** Handles minor camera vibration
3. **Higher match quality** than ByteTrack for overlapping people at doorways
4. **Ultralytics default:** Best-supported within the ecosystem

### Current Tuning is Good but Could Be Better

The tuned config has sensible adjustments:
- `track_high_thresh: 0.35` (stricter first match) -- good
- `new_track_thresh: 0.4` (fewer false tracks) -- good
- `track_buffer: 45` (1.5s at 30fps, 3s at 15fps) -- appropriate for brief occlusions

**Missing optimization:** ReID is disabled (`with_reid: False`). For entrance monitoring where people briefly occlude each other at a doorway, enabling lightweight ReID would significantly improve ID stability:

```yaml
with_reid: True
model: auto           # Uses YOLO detector features, minimal overhead
appearance_thresh: 0.3  # More aggressive matching on appearance
proximity_thresh: 0.6   # Trust proximity more in narrow spaces
```

### Known Issue: ID Reassignment

A documented Ultralytics community issue (#19784) describes ID reassignment problems with BoT-SORT and ByteTrack on webcam input. This is particularly relevant for entrances where:
- A person enters, leaves frame, returns -- gets new ID
- Two people pass each other at the doorway -- IDs may swap

**Mitigation strategies:**
1. Enable ReID (`with_reid: True`)
2. Increase `track_buffer` to maintain lost tracks longer
3. Use the system's per-person cooldown to prevent duplicate counting
4. The dual-zone approach inherently limits the tracking window

### Sources

- [Ultralytics Tracking Documentation](https://docs.ultralytics.com/modes/track/)
- [BoT-SORT + YOLO Explained - Labellerr](https://www.labellerr.com/blog/bot-sort-tracking/)
- [BoT-SORT vs ByteTrack Comparison](https://medium.com/pixelmindx/ultralytics-yolov8-object-trackers-botsort-vs-bytetrack-comparison-d32d5c82ebf3)
- [ID Reassignment Discussion #19784](https://github.com/orgs/ultralytics/discussions/19784)
- [Multi-Tracker Evaluation on Real-World Scenarios](https://www.veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios/)

---

## 7. Edge Deployment Optimization

**Confidence: MEDIUM-HIGH** (verified via official docs + research papers)

### Current Bottleneck

Running YOLOv8m at 1280px inference with PyTorch on CPU:
- Estimated ~235ms per frame = ~4 FPS
- This is far below the 15 FPS target

### Optimization Path (Priority Order)

#### 1. Switch to YOLO26n (Biggest Impact - No Cost)

| Metric | YOLOv8m@1280 | YOLO26n@640 | Improvement |
|--------|-------------|-------------|-------------|
| mAP | 50.2 | 40.9 | -9.3 (acceptable for entrance) |
| CPU Speed | ~235ms | ~39ms | **6x faster** |
| Params | 25.9M | 2.4M | **11x fewer** |

For entrance detection, 40.9 mAP on COCO translates to excellent person detection because:
- People are large objects (not small/medium COCO categories)
- Controlled environment (fixed camera angle, known lighting)
- Single class (person only)

#### 2. Export to Optimized Format

| Format | Target Hardware | Expected Speedup | Effort |
|--------|----------------|-------------------|--------|
| **ONNX** | Any CPU | 1.5-2x | Low |
| **OpenVINO** | Intel CPU/iGPU | 2-4x | Low |
| **TensorRT** | NVIDIA GPU | 3-10x | Medium |
| **NCNN** | ARM CPU (RPi) | 1.5-2x | Medium |
| **CoreML** | Apple Silicon | 2-3x | Low |

**Recommendation for this project:** Export to ONNX first (universal), then OpenVINO if deploying on Intel mini-PC or NCNN if deploying on Raspberry Pi.

```python
from ultralytics import YOLO
model = YOLO("yolo26n.pt")
model.export(format="onnx")     # or "openvino", "ncnn"
```

#### 3. Reduce Inference Resolution

Currently using 1280px. For person detection at a doorway:
- **640px is sufficient** for most entrance cameras
- **480px** may work for close-range cameras
- This alone gives ~4x speedup (quadratic with resolution)

#### 4. Frame Skipping / Adaptive Processing

At 15 FPS, not every frame needs full inference:
- Process every 2nd frame: 7.5 FPS effective detection rate (still adequate)
- Use lightweight motion detection to trigger full inference only when movement detected
- Track interpolation between detection frames

### Raspberry Pi 5 Performance Estimates

Based on published benchmarks (YOLO11n on RPi5):

| Format | Model | FPS |
|--------|-------|-----|
| PyTorch | YOLO11n | ~3 FPS |
| OpenVINO | YOLO11n | ~12 FPS |
| NCNN | YOLO11n | ~3.4 FPS |
| ONNX | YOLO11n | ~8 FPS |

YOLO26n should be comparable or faster. With 640px inference and OpenVINO, **~12-15 FPS is achievable on Raspberry Pi 5**.

### Sources

- [YOLO11 on Raspberry Pi - LearnOpenCV](https://learnopencv.com/yolo11-on-raspberry-pi/)
- [Ultralytics Model Export Guide](https://docs.ultralytics.com/modes/export/)
- [Ultralytics Deployment Options](https://docs.ultralytics.com/guides/model-deployment-options/)
- [YOLO on NCNN Performance Analysis](https://blog.gopenai.com/yolo-models-on-ncnn-faster-or-slower-a-technical-breakdown-03d36612c921)

---

## 8. Similar Open-Source Projects

**Confidence: MEDIUM** (GitHub survey, varying project quality)

### Notable Projects

| Project | Approach | YOLO Version | Tracker | Stars | Notes |
|---------|----------|-------------|---------|-------|-------|
| [IdoGalil/People-counting-system](https://github.com/IdoGalil/People-counting-system) | YOLO + CSRT tracker | YOLOv3 | DCF-CSRT | ~200 | Mature, well-documented |
| [Deepchavda007/People-Count-using-YOLOv8](https://github.com/Deepchavda007/People-Count-using-YOLOv8) | YOLO + centroid counting | YOLOv8 | Centroid | ~50 | Simple line-crossing |
| [renatocastro33/People-Detection-and-Counting-In-Out-Line](https://github.com/renatocastro33/People-Detection-and-Counting-In-Out-Line) | YOLO + DeepSORT + line | YOLOv3 | DeepSORT | ~100 | Direction-aware |
| [SmitSheth/People-Counter](https://github.com/SmitSheth/People-Counter) | YOLO + tripline | YOLO | Custom | ~80 | Tripline-based |
| [zaki1003/YOLO-CROWD](https://github.com/zaki1003/YOLO-CROWD) | Lightweight crowd counting | YOLOv5s | N/A | ~200 | Edge-optimized |

### How This Project Compares

The clinic-entrance-detector is **significantly more sophisticated** than most open-source people counters:

1. **Multi-factor scoring** (most projects use simple line-crossing)
2. **Dual-zone temporal validation** (unique to this project)
3. **Velocity consistency analysis** (not found in any comparable project)
4. **Built-in calibration tool** (most projects require manual coordinate entry)
5. **Webhook integration** with cooldown/retry logic
6. **Live dashboard** with WebSocket streaming
7. **Fine-tuning pipeline** (data collection + training)

The closest comparable commercial systems (not open-source) are from Axis Communications, Hikvision, and Dahua, which use similar zone-based approaches but with proprietary algorithms.

### Ultralytics Built-in Solutions

The biggest "competitor" is now Ultralytics' own built-in solutions:

```python
from ultralytics import solutions

# Line-based counting
counter = solutions.ObjectCounter(
    show=True,
    region=[(300, 400), (900, 400)],  # Line: 2 points
    model="yolo26n.pt",
    show_in=True,
    show_out=True,
)

# Zone-based counting
region_counter = solutions.RegionCounter(
    show=True,
    region=[(50, 50), (250, 50), (250, 250), (50, 250)],
    model="yolo26n.pt",
)
```

**Trade-off:** Built-in solutions are simpler but lack the multi-factor scoring, dwell time analysis, and webhook integration that make this project production-ready.

### Sources

- [GitHub People Counter Topic](https://github.com/topics/people-counter)
- [Ultralytics ObjectCounter](https://docs.ultralytics.com/guides/object-counting/)
- [Ultralytics RegionCounter](https://docs.ultralytics.com/guides/region-counting/)

---

## 9. False Positive Reduction

**Confidence: MEDIUM** (combination of research and domain reasoning)

### Common False Positive Sources at Entrances

| Source | Frequency | Current Mitigation | Additional Mitigation |
|--------|-----------|-------------------|----------------------|
| **Reflections in glass doors** | High | Confidence threshold (0.4) | Increase to 0.5, add bbox size filter |
| **Shadows of people outside** | Medium | Zone A->B temporal ordering | Add minimum bbox height filter |
| **People passing by without entering** | High | Velocity consistency + dwell | Working well in current system |
| **Delivery packages/carts** | Low | Class filter (person only) | Working correctly |
| **Door opening/closing motion** | Medium | Confidence threshold | Add minimum track age before scoring |
| **Multiple people entering together** | Medium | Per-person scoring | Enable ReID for better ID separation |
| **Child/pet at foot level** | Low | Bottom-center anchor point | Add minimum bbox area filter |

### Current System's False Positive Handling (Strengths)

1. **Multi-factor scoring requires multiple signals to converge** -- single anomalies don't trigger
2. **Track age guard (0.5s minimum)** prevents instant false triggers
3. **Dwell time bounds** filter transient detections
4. **Velocity consistency** requires sustained directional movement
5. **Per-person and global cooldowns** prevent duplicate events
6. **ID cooldown map** prevents same-ID re-triggering

### Recommended Improvements

1. **Minimum bbox area filter:** Add a configurable minimum detection area (e.g., 5000 pixels squared at 1280x720) to filter tiny/distant false detections

2. **Confidence hysteresis:** Use higher confidence to start tracks (current: `new_track_thresh: 0.4`) but lower to maintain (current: `track_low_thresh: 0.15`). The current config already does this well.

3. **Zone B area ratio:** Only count Zone B if the bbox occupies at least 10-15% of Zone B's area. This filters distant detections that technically overlap the zone.

4. **Background subtraction pre-filter:** For static cameras, subtract the static background and only run YOLO on regions with motion. This dramatically reduces false positives from reflections/shadows.

5. **Temporal smoothing:** Require the "entering" classification to persist for N consecutive frames before emitting an event (the current 5-frame Zone B requirement partially does this).

### Research-Backed Techniques

- **Rapid-YOLO** (2022): Novel NMS using chaotic whale optimization reduces false bounding box detections
- **Dark-YOLO** (2025): Adaptive image enhancement module restores information in challenging conditions
- **YOLOv8's higher precision** over YOLOv5: Better at minimizing false positives while maintaining recall

### Sources

- [Decreasing YOLO False Positives - Ultralytics](https://github.com/ultralytics/yolov5/issues/666)
- [YOLO Background Detection Issues](https://community.ultralytics.com/t/yolo-v8-consider-the-background-as-a-target-what-can-i-do-about-that/1710/16)
- [Dark-YOLO for Low-Light Detection](https://www.mdpi.com/2076-3417/15/9/5170)

---

## 10. Night/Lighting Challenges

**Confidence: MEDIUM** (research-supported, not directly verified in this codebase)

### Challenges Specific to Clinic Entrances

1. **Backlighting from outside:** Bright exterior + dim interior creates silhouettes
2. **Automatic lighting changes:** Lights turning on/off as people enter
3. **Glass door reflections:** Varying with outdoor lighting
4. **Seasonal variation:** Summer evenings vs winter darkness
5. **Emergency lighting:** Different spectrum/intensity

### Mitigation Strategies

#### Software-Level (Recommended Priority)

1. **Image preprocessing pipeline:** Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) before YOLO inference:
   ```python
   import cv2
   clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
   lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
   lab[:, :, 0] = clahe.apply(lab[:, :, 0])
   frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
   ```

2. **Auto white balance and exposure normalization:** Standardize frames before inference

3. **Data augmentation during fine-tuning:** Include varied lighting conditions in training data (the current fine-tuning pipeline should use aggressive brightness/contrast augmentation)

4. **YOLO26 inherent robustness:** Later YOLO versions show improved robustness to lighting variation without explicit preprocessing

#### Hardware-Level

1. **IR illuminator + camera:** Best single investment for night operation
2. **Wide Dynamic Range (WDR) camera:** Handles backlighting from glass doors
3. **Proper camera positioning:** Avoid pointing directly at exterior light sources

### Research Finding

YOLOv8m "performs exceptionally well in challenging low-light conditions, consistently identifying small and distant objects with high precision" in nighttime surveillance applications. The medium model's robustness is one argument for keeping it, but YOLO26 small/medium models offer the same robustness with better efficiency.

### Sources

- [Dark-YOLO Algorithm](https://www.mdpi.com/2076-3417/15/9/5170)
- [Night-Time Surveillance with YOLOv8](https://www.iieta.org/journals/ijsse/paper/10.18280/ijsse.140611)
- [Low-Light YOLO Detection Evaluation](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ccs2.12114)

---

## 11. Multi-Camera and Depth Sensor Approaches

**Confidence: MEDIUM** (research-supported, hardware-dependent)

### When to Consider Alternatives to Single RGB Camera

| Scenario | Solution | Cost | Accuracy Gain |
|----------|----------|------|--------------|
| High traffic (>10 people/minute) | Multi-camera + fusion | $$$ | Moderate |
| Extreme lighting variation | Thermal/IR camera | $$ | High |
| Narrow doorway with occlusion | Depth sensor (overhead) | $$ | High |
| Glass doors with reflections | Overhead depth sensor | $$ | Very high |
| Need both identity + direction | RGB + depth fusion | $$$ | Very high |

### Overhead Depth Sensor (Top-Down)

The most reliable entrance counting approach in commercial systems uses **overhead-mounted depth sensors** (time-of-flight):

- **Intel RealSense D435i** (~$200): Stereo depth, works indoors up to 10m
- **Intel RealSense L515** (~$350, discontinued): LiDAR-based, 9m range, high accuracy
- Immune to lighting variation
- Can count in complete darkness
- Better at separating closely-spaced people

**Trade-off:** Does not provide person identification, only blob counting. Works best combined with RGB for identity.

### For This Clinic: Single Camera is Appropriate

Given the use case (single entrance, moderate traffic, webhook trigger for video workflow):
- A single overhead or angled RGB camera with YOLO is sufficient
- The system's sophistication (dual-zone, multi-factor scoring) compensates for single-camera limitations
- Adding depth sensing is unnecessary complexity for the current requirements

### Future Enhancement Path

If accuracy needs increase:
1. First: Optimize the existing system (YOLO26, ReID, export optimization)
2. Then: Add an IR illuminator for night operation
3. Then: Consider WDR camera upgrade
4. Only if needed: Add overhead depth sensor for occlusion handling

### Sources

- [Intel RealSense for People Counting](https://github.com/ultralytics/ultralytics/issues/607)
- [LiDAR vs Depth Camera Comparison](https://us.keyirobot.com/blogs/buying-guide/lidar-vs-depth-camera-choosing-the-right-sensor-for-robot-vision)

---

## 12. Recommendations Summary

### Immediate Improvements (Low Effort, High Impact)

| # | Change | Impact | Effort |
|---|--------|--------|--------|
| 1 | **Upgrade to YOLO26n** from YOLOv8m | 6x faster inference, competitive accuracy | Low - just change model name |
| 2 | **Reduce inference resolution to 640px** | ~4x faster (combined with #1: ~24x faster) | Low - change config |
| 3 | **Enable BoT-SORT ReID** (`with_reid: True, model: auto`) | Better ID stability at doorway | Low - edit YAML |
| 4 | **Fix .env/config.py model mismatch** | Prevent deployment confusion | Low - align configs |
| 5 | **Make Zone B split configurable** | Per-site optimization | Low - add env var |

### Medium-Term Improvements

| # | Change | Impact | Effort |
|---|--------|--------|--------|
| 6 | **Export model to ONNX/OpenVINO** | 2-4x additional speedup on CPU | Medium |
| 7 | **Add CLAHE preprocessing** | Better low-light performance | Medium |
| 8 | **Add minimum bbox area filter** | Fewer false positives from distant objects | Low-Medium |
| 9 | **Use Supervision LineZone** for tripwire | Simpler, better-tested tripwire logic | Medium |
| 10 | **Add background subtraction pre-filter** | Reduce false positives from static reflections | Medium |

### Long-Term / Architecture Changes

| # | Change | Impact | Effort |
|---|--------|--------|--------|
| 11 | **Consider Ultralytics ObjectCounter** as alternative | Major simplification | High (rewrite) |
| 12 | **Add IR illumination** for night | Robust night operation | Medium (hardware) |
| 13 | **Persist track state across restarts** | No count loss on restart | Medium |
| 14 | **Add frame skip / motion-triggered inference** | Reduce idle CPU usage | Medium |
| 15 | **Fine-tune YOLO26n on clinic data** | Maximize detection accuracy | Medium (use existing pipeline) |

### Priority Order for Implementation

1. Fix .env/config.py alignment (immediate)
2. Upgrade to YOLO26n at 640px (immediate, massive speedup)
3. Enable ReID in BoT-SORT (immediate, better tracking)
4. Make Zone B split configurable (quick win)
5. Export to ONNX (medium-term, edge deployment)
6. Add CLAHE preprocessing (if lighting is an issue)
7. Fine-tune on clinic-specific data (when enough training data collected)

### What NOT to Change

- **Keep the dual-zone approach:** It is well-designed and more robust than simple line-crossing
- **Keep the multi-factor scoring:** Unique strength, no comparable open-source alternative
- **Keep BoT-SORT over ByteTrack:** Better accuracy for entrance scenarios
- **Keep the calibration tool:** Essential for deployment flexibility
- **Keep the webhook architecture:** Clean integration with the VLC controller workflow

---

## Appendix: Key URLs and References

### Official Documentation
- [Ultralytics YOLO26 Docs](https://docs.ultralytics.com/models/yolo26/)
- [Ultralytics Object Counting](https://docs.ultralytics.com/guides/object-counting/)
- [Ultralytics Region Counting](https://docs.ultralytics.com/guides/region-counting/)
- [Ultralytics Tracking Docs](https://docs.ultralytics.com/modes/track/)
- [Ultralytics Model Export](https://docs.ultralytics.com/modes/export/)
- [Ultralytics Deployment Options](https://docs.ultralytics.com/guides/model-deployment-options/)
- [Ultralytics YOLO26 vs YOLO11](https://docs.ultralytics.com/compare/yolo26-vs-yolo11/)

### Research Papers
- [Evaluation of YOLO architectures for person detection and counting (2025)](https://link.springer.com/article/10.1007/s11042-025-20662-z)
- [Dark-YOLO: Low-Light Object Detection (2025)](https://www.mdpi.com/2076-3417/15/9/5170)
- [Night-Time Surveillance with YOLOv8 (2024)](https://www.iieta.org/journals/ijsse/paper/10.18280/ijsse.140611)
- [YOLO Evolution Overview (2025)](https://arxiv.org/html/2510.09653v2)
- [YOLOv12 Performance Comparison (2025)](https://arxiv.org/html/2504.11995v1)

### Open Source Projects
- [People-counting-system (YOLO+CSRT)](https://github.com/IdoGalil/People-counting-system)
- [People-Count-using-YOLOv8](https://github.com/Deepchavda007/People-Count-using-YOLOv8)
- [Multi-tracker Evaluation](https://github.com/OmriGrossman/multi-tracker-evaluation)
- [BoT-SORT Original Repo](https://github.com/NirAharon/BoT-SORT)

### Community Discussions
- [BoT-SORT vs ByteTrack Comparison](https://medium.com/pixelmindx/ultralytics-yolov8-object-trackers-botsort-vs-bytetrack-comparison-d32d5c82ebf3)
- [ID Reassignment in BoT-SORT/ByteTrack](https://github.com/orgs/ultralytics/discussions/19784)
- [Tracker Parameter Tuning](https://github.com/ultralytics/ultralytics/issues/4473)
- [YOLO on Edge Devices](https://learnopencv.com/yolo11-on-raspberry-pi/)
