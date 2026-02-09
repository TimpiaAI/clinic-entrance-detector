# Clinic Entrance Detection System

A production-oriented local vision service that watches a clinic entrance camera, tracks people with YOLOv8 + ByteTrack, and triggers webhooks only when a person actually enters (approaches camera and crosses a calibrated tripwire), while ignoring sidewalk/hallway passersby.

## How It Works

```text
Camera Frame
  |
  |-- YOLOv8n person detections (class=person)
  |
  |-- ByteTrack IDs over time
  |
  |-- Entry Analyzer per ID:
       1) bbox growth ratio (approaching camera)
       2) directional movement toward camera
       3) dwell time inside entry zone
       4) tripwire crossing in configured direction
  |
  |-- score >= threshold + tripwire crossed => person_entered
  |
  |-- async webhook queue (retry + HMAC + cooldown)
  |
  |-- dashboard (live stream + stats + calibration)
```

## Hardware Needed

- Wall-mounted camera facing entrance door (USB webcam or RTSP IP camera)
- Mini PC / edge box (x86 or ARM) running Python 3.11+
- Stable network for webhook delivery

## Project Structure

```text
clinic-entrance-detector/
├── main.py
├── config.py
├── detector/
│   ├── person_tracker.py
│   ├── entry_analyzer.py
│   └── zone_config.py
├── webhook/
│   └── sender.py
├── calibration/
│   └── calibration_tool.py
├── dashboard/
│   ├── web.py
│   └── templates/
│       ├── index.html
│       └── calibrate.html
├── utils/
│   ├── video_stream.py
│   ├── snapshot.py
│   └── logger.py
├── tests/
│   ├── test_with_webcam.py
│   └── test_with_video.py
├── requirements.txt
├── config.env.example
├── Dockerfile
├── docker-compose.yml
└── deploy/clinic-entrance-detector.service
```

## Installation

```bash
cd clinic-entrance-detector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.env.example .env
```

## First-Time Calibration

### Desktop calibration tool (OpenCV)

```bash
python main.py --calibrate
```

- Press `z`: draw entry zone rectangle
- Press `t`: click two points for tripwire
- Press `d`: cycle entry direction (`top_to_bottom` for most wall-facing setups)
- Press `s`: save calibration
- Press `q`: exit

### Web calibration tool

1. Start detector: `python main.py`
2. Open `http://localhost:8080/calibrate`
3. Draw entry zone and tripwire on live feed
4. Select entry direction
5. Click Save

Screenshot placeholders:

- `docs/screenshots/calibration-zone.png`
- `docs/screenshots/calibration-tripwire.png`
- `docs/screenshots/dashboard-live.png`

## Run Commands

```bash
# Run with webcam
python main.py

# Run with RTSP
python main.py --source rtsp --url "rtsp://admin:pass@192.168.1.100:554/stream1"

# Run with local file
python main.py --source file --video entrance_recording.mp4

# Run without dashboard
python main.py --no-dashboard

# Optional local preview window
python main.py --show-window

# Show extra raw detection boxes + scoring debug
python main.py --show-window --debug-boxes

# Collect training data (interactive)
python main.py --collect-data --show-window --source webcam --dataset-dir datasets/clinic_person

# Fine-tune model on collected data
python main.py --train-model --dataset-dir datasets/clinic_person --train-epochs 50 --train-device cpu

# Use trained model for runtime detection
YOLO_MODEL=runs/train/clinic_person_finetune/weights/best.pt python main.py --show-window --debug-boxes
```

Dashboard URLs:

- Live dashboard: `http://localhost:8080`
- Calibration page: `http://localhost:8080/calibrate`

## Training Mode (Improve Detection Accuracy)

When camera perspective is unusual, collect local samples and fine-tune YOLO for your entrance scene.

### 1) Collect dataset

```bash
python main.py --collect-data --source webcam --dataset-dir datasets/clinic_person
```

Collector controls:

- `space`: pause/resume frame
- `left mouse drag`: draw a person label box
- `right click`: remove nearest label box
- `p`: copy YOLO proposals into labels
- `c`: clear current labels
- `a`: toggle auto-save proposals when no manual labels exist
- `s`: save current frame + labels
- `q`: quit

Dataset structure created automatically:

- `datasets/clinic_person/images/train`
- `datasets/clinic_person/images/val`
- `datasets/clinic_person/labels/train`
- `datasets/clinic_person/labels/val`

### 2) Train model

```bash
python main.py --train-model --dataset-dir datasets/clinic_person --train-epochs 50 --train-imgsz 640 --train-batch 16 --train-device cpu
```

Notes:

- Minimum recommended data: at least 20 train images and 5 val images.
- Every image must have a matching YOLO `.txt` label.

### 3) Run detector with trained weights

```bash
YOLO_MODEL=runs/train/clinic_person_finetune/weights/best.pt python main.py --show-window --debug-boxes
```

## Detection Logic

A person is marked `entering` when weighted confidence is high enough and tripwire crossing is in the configured entry direction.

`score = bbox(0.4) + y/x movement(0.3) + dwell(0.2) + tripwire(0.1)`

Defaults:

- `BBOX_GROWTH_RATIO=1.3`
- `Y_MOVEMENT_THRESHOLD=50`
- `DWELL_TIME_MIN=1.5`
- `DWELL_TIME_MAX=15.0`
- `ENTRY_CONFIDENCE_THRESHOLD=0.6`

## Configuration Reference

All values are in `.env` and loaded by `python-dotenv`:

- Video: `VIDEO_SOURCE`, `WEBCAM_INDEX`, `RTSP_URL`, `VIDEO_FILE`, `FRAME_WIDTH`, `FRAME_HEIGHT`, `TARGET_FPS`
- Model/tracking: `YOLO_MODEL`, `YOLO_CONFIDENCE`, `YOLO_CLASSES`, `TRACKER`
- Entry scoring: `BBOX_GROWTH_RATIO`, `Y_MOVEMENT_THRESHOLD`, `DWELL_TIME_MIN`, `DWELL_TIME_MAX`, `ENTRY_CONFIDENCE_THRESHOLD`
- Webhooks: `WEBHOOK_URL`, `WEBHOOK_TIMEOUT`, `WEBHOOK_RETRY_COUNT`, `WEBHOOK_RETRY_DELAY`, `WEBHOOK_COOLDOWN_PERSON`, `WEBHOOK_COOLDOWN_GLOBAL`, `WEBHOOK_INCLUDE_SNAPSHOT`, `WEBHOOK_SECRET`
- Cleanup: `PERSON_TIMEOUT`, `MAX_TRACKED_PERSONS`, `ENTRY_LOG_SIZE`
- Dashboard: `DASHBOARD_HOST`, `DASHBOARD_PORT`
- Calibration: `CALIBRATION_FILE`
- Metadata/logging: `CAMERA_ID`, `LOG_LEVEL`

## Webhook Integration

### Payload

```json
{
  "event": "person_entered",
  "timestamp": "2026-02-09T14:30:15.123456+00:00",
  "confidence": 0.85,
  "person_id": 42,
  "detection_details": {
    "bbox_growth_ratio": 1.45,
    "y_movement_pixels": 82,
    "dwell_time_seconds": 2.3,
    "entry_zone_time": 2.3,
    "direction_scores": {
      "bbox_size": 0.4,
      "y_movement": 0.3,
      "dwell_time": 0.2,
      "tripwire": 0.1
    }
  },
  "snapshot": "<base64_jpeg>",
  "metadata": {
    "camera_id": "clinic_entrance_01",
    "frame_number": 15432,
    "total_entries_today": 28
  }
}
```

### Reliability behavior

- Async queue-based sender in background worker
- Retries with exponential backoff (`WEBHOOK_RETRY_COUNT`, `WEBHOOK_RETRY_DELAY`)
- Request timeout (`WEBHOOK_TIMEOUT`)
- Cooldowns:
  - per person: `WEBHOOK_COOLDOWN_PERSON`
  - global spacing: `WEBHOOK_COOLDOWN_GLOBAL`
- Additional burst spacing: 1 second between queued sends

### HMAC verification

If `WEBHOOK_SECRET` is set, each request includes:

- Header: `X-Signature: sha256=<hex_digest>`
- Digest over raw JSON body using HMAC-SHA256

Receiver pseudo-check:

```python
import hashlib
import hmac

expected = "sha256=" + hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
valid = hmac.compare_digest(expected, request.headers["X-Signature"])
```

## Dashboard API

- `GET /` live dashboard
- `GET /calibrate` calibration UI
- `GET /video_feed` MJPEG stream
- `GET /api/state` current stats/state
- `GET /api/calibration` current calibration
- `POST /api/calibration` save calibration
- `POST /api/test-webhook` queue webhook test
- `WS /ws` real-time state updates

WebSocket messages include FPS, tracked persons, recent events, webhook status, uptime, and calibration snapshot.

## Testing

### Webcam test

```bash
python tests/test_with_webcam.py
```

- Walk toward camera in entry zone: should print `ENTERING DETECTED`
- Walk left/right past zone: should mostly remain `PASSING` / ignored

### Video test

```bash
python tests/test_with_video.py --video ./samples/entrance.mp4 --output ./annotated.mp4
```

Produces annotated output and prints event timestamps.

## Deployment

### Docker

```bash
docker compose up --build -d
```

Notes:

- Mount camera device (example `/dev/video0`)
- Provide `.env` file next to compose file
- Persist `calibration.json`

### systemd

1. Copy service file:
   `sudo cp deploy/clinic-entrance-detector.service /etc/systemd/system/`
2. Adjust `WorkingDirectory`, `ExecStart`, and `.env` path
3. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clinic-entrance-detector
sudo systemctl start clinic-entrance-detector
sudo systemctl status clinic-entrance-detector
```

## Troubleshooting

- False positives on passersby:
  - Tighten entry zone around door
  - Increase `ENTRY_CONFIDENCE_THRESHOLD` to `0.65-0.75`
  - Increase `Y_MOVEMENT_THRESHOLD`
- Missed entries:
  - Lower `YOLO_CONFIDENCE` (e.g. `0.4`)
  - Lower `BBOX_GROWTH_RATIO` (e.g. `1.2`)
  - Verify tripwire placement and entry direction
- Person lingers in doorway:
  - Increase `DWELL_TIME_MAX` slightly
- High CPU:
  - Reduce `FRAME_WIDTH/HEIGHT`
  - Lower `TARGET_FPS`
- Webhook failures:
  - Check endpoint reachability
  - Inspect `last_error` in dashboard state
  - Verify HMAC secret alignment

## License

MIT
