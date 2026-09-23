# AI CCTV Fire & Smoke Monitoring Platform - Backend Service

Enterprise Python backend for real-time CCTV stream processing, OpenCV computer vision integration, RTSP NVR/DVR ingestion, and Fire & Smoke alert management.

---

## Technical Stack

- **Language**: Python 3.12+
- **API Framework**: FastAPI & Uvicorn
- **Database & Migrations**: PostgreSQL, SQLAlchemy ORM, Alembic
- **Computer Vision**: OpenCV (Headless)
- **Validation & Settings**: Pydantic v2 & Pydantic-Settings
- **Structured Logging**: Standard Python Logging with file rotation & request correlation ID tracking

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                   # FastAPI Application initialization & middleware assembly
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # Pydantic environment configuration & CORS validation
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py         # Main API v1 router aggregator
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py     # Liveness (/health) and Readiness (/ready) endpoints
│   │           ├── cameras.py    # RTSP Camera REST API skeleton
│   │           └── alerts.py     # Fire/Smoke Alert REST API skeleton
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py             # Health & Ready response Pydantic models
│   │   ├── camera.py             # Camera request/response models with credential masking
│   │   ├── alert.py              # Alert models
│   │   └── common.py             # Standardized success/error JSON response envelopes
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py            # SQLAlchemy engine, SessionLocal, and DB ping function
│   │   └── base.py               # Declarative ORM base class
│   ├── models/                   # Future ORM models (Camera, Alert, Recording)
│   ├── camera/                   # RTSP stream decoding & frame ingestion engine (Phase 2+)
│   ├── detection/                # AI model inference pipeline (Phase 2+)
│   ├── alerts/                   # Alert event processor (Phase 2+)
│   ├── recording/                # Evidence image & clip recorder (Phase 2+)
│   ├── services/                 # Business logic service layer
│   ├── websocket/
│   │   ├── __init__.py
│   │   ├── connection_manager.py # Real-time alert push notification connection manager
│   │   └── router.py             # WebSocket alert endpoint (/ws/v1/alerts)
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── request_id.py         # Correlation ID middleware generating/propagating X-Request-ID
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Structured logger writing to console & logs/app.log
│       ├── security.py           # RTSP URL credential masking sanitizer
│       └── exceptions.py         # Custom exceptions & global FastAPI error handlers
├── alembic/                      # Database migration scripts & environment
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
│   ├── __init__.py
│   └── test_health.py            # Pytest test suite for health, ready, & middleware
├── evidence/                     # Directory for evidence snapshot storage
├── recordings/                   # Directory for video clip storage
├── logs/                         # Application log storage
├── alembic.ini                   # Alembic migration configuration
├── .env.example                  # Environment configuration template
├── .env                          # Local environment settings
├── .gitignore                    # Git ignore configuration
├── .dockerignore                 # Docker build ignore configuration
├── requirements.txt              # Python dependencies lockfile
└── README.md                     # Backend documentation
```

---

## Installation & Setup Instructions

### 1. Prerequisites
- Python 3.12 or later installed.
- (Optional) PostgreSQL server installed locally or running via Docker.

### 2. Create Virtual Environment & Install Dependencies

On Windows (PowerShell):
```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install required dependencies
pip install -r requirements.txt
```

On Linux / macOS:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running Database Migrations with Alembic

If PostgreSQL is running and configured in `.env`:

```bash
# Run database migrations to head
alembic upgrade head

# Generate a new migration revision
alembic revision --autogenerate -m "create_initial_tables"
```

---

## Starting the Application Server

Start the FastAPI application using Uvicorn:

```bash
# Run server with live reload enabled
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Server will start at: `http://127.0.0.1:8000`
OpenAPI Documentation: `http://127.0.0.1:8000/docs`
ReDoc Documentation: `http://127.0.0.1:8000/redoc`

---

## Testing Health & System Endpoints

### 1. Liveness Check (`/health`)
Checks if the application server is up.

```bash
curl -i http://127.0.0.1:8000/health
```

Expected Response (`HTTP 200 OK`):
```json
{
  "status": "healthy",
  "app_name": "AI CCTV Fire & Smoke Monitor",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "2026-08-17T15:50:00Z"
}
```

### 2. Readiness Check (`/ready`)
Checks database connection and dependency status.

```bash
curl -i http://127.0.0.1:8000/ready
```

Expected Response (`HTTP 200 OK` when DB connected, `HTTP 503` when disconnected):
```json
{
  "status": "ready",
  "database": "connected",
  "dependencies": {
    "postgresql": "connected"
  },
  "timestamp": "2026-08-17T15:50:00Z"
}
```

### 3. Automated Test Suite Execution

Run pytest:

```bash
pytest tests/ -v
```

---

## Architectural Breakdown & File Responsibilities

| File / Component | Responsibility |
| :--- | :--- |
| `app/main.py` | Assembles application factory, mounts CORS, registers custom handlers, includes routers, and controls lifespan context. |
| `app/config/settings.py` | Central settings management using Pydantic BaseSettings, loading parameters from `.env`. |
| `app/middleware/request_id.py` | Intercepts requests, generates `X-Request-ID`, stores in `contextvars`, logs ID, and returns in headers. |
| `app/utils/logger.py` | Structured console & file rotating logger including timestamp, log level, request_id, and line numbers. |
| `app/utils/security.py` | Regex-based RTSP URL credential sanitizer ensuring passwords are standardly masked as `***`. |
| `app/utils/exceptions.py` | Maps custom exceptions, HTTP errors, and unhandled errors into standardized JSON error envelopes. |
| `app/database/session.py` | Configures SQLAlchemy engine with `pool_pre_ping=True`, session factory, and database ping utility. |
| `app/schemas/` | Defines Pydantic input/output schemas with automatic credential sanitization and standardized error structures. |
| `app/websocket/connection_manager.py` | Handles WebSocket client registration and broadcasting real-time alert events (notifications ONLY). |

---

## Detection Accuracy & Speed Engineering

The fire / smoke / PPE detectors are tuned around one principle: **report broadly, alert narrowly**.
A candidate is surfaced (overlay, WebSocket telemetry, detection log) from a relaxed floor so nothing
is silently discarded, while an *alert* (email, webhook, incident, evidence clip) additionally requires
the temporal state machine to see the same physical region across consecutive frames. Sensitivity and
alarm trust are therefore decoupled instead of being traded against each other by a single threshold.

### What was measured and fixed

All figures below were produced by running the bundled weights (`models/fire_smoke.onnx`,
`models/ppe.onnx`, `models/yolov8n.onnx`) over real imagery through `FramePipeline`.
See *Validating on your own footage* below to reproduce them on your hardware.

| Problem found | Root cause | Fix |
| :--- | :--- | :--- |
| Real fires and smoke produced **zero** detections (0 of 4 fire scenes) | The model's score was passed through a hard colour gate (`_verify_flame_chromaticity`) that rejected anything below 0.92 confidence; genuine blazes scored 0.15-0.61 | Physics is now a *booster*, not a gate: corroboration lifts weak-but-real evidence, structure (long straight edges) suppresses man-made surfaces. 3 of the 4 scenes now detect |
| `Person` boxes vanished next to `Safety Vest` boxes | `cv2.dnn.NMSBoxes` is class agnostic - a vest box overlapping its worker suppressed the worker | Class-aware vectorised NMS (`app/detection/nms.py`) |
| One hard hat produced 12 overlapping boxes; workers were counted twice | Low candidate threshold + plain NMS with no duplicate fusion | Weighted Box Fusion merges same-class clusters into one score-weighted box and reports an agreement count |
| Phantom workers on scenes with **nobody** in them (fixed 0.86-0.88 confidence) | The OpenCV Haar/skin fallback ran whenever the model found no persons - i.e. exactly on empty scenes - and each phantom worker became a phantom PPE violation | Fallbacks only run when no neural backend exists at all |
| Every worker was labelled "Safety Glasses Found" at 0.95-0.96 confidence, including firemen in helmets | A geometric CV heuristic (`_detect_glasses_cv`) fabricated glasses from brow-bar/rim patterns | Disabled on the neural path; replaced by model-based worker-crop refinement. `ENABLE_CV_GLASSES_FALLBACK_ON_NEURAL_PATH` restores it if you want it |
| Safety glasses never detected (model scored 0.116) | Glasses occupy ~4 px in a 640-px full-frame pass | Worker-crop refinement re-runs the network on the head crop, where the same glasses score 0.25-0.42. Verified end-to-end: `goggles` now appears in the pipeline output |
| Worker wearing a high-vis vest was flagged as non-compliant | The bundled PPE weights have near-zero recall for a back-facing vest (measured 0.00 at both full frame and torso crop) | Hi-vis corroboration: fluorescent fabric **plus** retroreflective silver band, measured inside the worker's torso box only. Clears a false violation; can never create one |
| Events cleared or raised because of scheduler timing | Gated frames fed the association engine an empty PPE list (fabricating violations) and the PPE state machine an empty analysis list (clearing live violations) | No fresh evidence means no state change; previous conclusions are reused for a bounded window |
| First inference after each start stalled for 100-400 ms | No warm-up, fresh ORT memory arena | Session warm-up on load + singleton session cache |

### Speed

| Scenario | Behaviour |
| :--- | :--- |
| Empty, motionless scene | Worker and PPE networks are skipped entirely (verified: 26.5 ms/frame, ~38 FPS on a 2-vCPU host, versus a periodic re-confirmation sweep before). A guaranteed sweep every `AI_MOTION_SWEEP_SECONDS` keeps a stale background model from hiding an intruder |
| Scene with workers | The worker branch runs on a **measured** cadence: `_observe_worker_cost` tracks the branch's true cost and schedules the next run slightly above it. A fixed interval makes the system request work it cannot finish, which backs up the queue and delivers stale alerts |
| ROI refinement cost | Refinement only runs for items that are *missing* (never for compliant workers), on one body region per invocation, on every Nth worker frame (`PPE_ROI_REFINE_EVERY_N`), with TTL-cached conclusions. A confirmed item is not re-checked for several seconds |
| Post-processing | Fully vectorised decode; a per-class candidate cap bounds fusion cost on pathological frames |
| ONNX Runtime | 2-4 intra-op threads (never `cores - 2` per session across three sessions), arena and memory-pattern reuse, `ORT_ENABLE_ALL` graph optimisation |

### Validating on your own footage

```bash
# Accuracy + latency against labelled frames (label 20-50 frames per scene)
python scripts/validate_detection.py --images ./my_frames --labels ./my_frames/labels.json --out ./annotated

# Throughput on an idle versus occupied scene
python scripts/validate_detection.py --benchmark
```

The labels format is documented at the top of the script. An image with an empty label object is
treated as a negative, so the tool reports the metric that matters operationally: how often a camera
that should be quiet raises something.

### Tuning cheat-sheet

| Symptom | Knob |
| :--- | :--- |
| Too many fire/smoke alerts | Raise `FIRE_ALERT_CONFIDENCE` / `SMOKE_ALERT_CONFIDENCE`; detections stay visible |
| Missing real fire/smoke | Raise `FIRE_CANDIDATE_CONFIDENCE` only if you see noise; lower `FIRE_STRUCTURE_EDGE_RATIO` to be stricter about brick/glass/grille textures |
| Missing safety glasses on distant workers | Lower `GLASSES_CONFIDENCE_THRESHOLD`, set `PPE_ROI_REFINE_EVERY_N=1`, raise `PPE_CROP_REFINE_MAX_PERSONS` |
| Missed vests on back-facing workers | `VEST_HIVIS_MIN_COLOR_RATIO` / `VEST_HIVIS_MIN_SILVER_RATIO` (lower to catch more, raise to be stricter) |
| CPU saturated / low FPS | Raise `PPE_INFERENCE_INTERVAL_SEC`, set `PPE_ROI_REFINE_EVERY_N=3`, disable `ENABLE_PERSON_ROI_REFINE` |
| Slower hardware than expected | Check `pipeline.performance_stats()` for the measured worker-branch cost; set `PPE_ADAPTIVE_CADENCE=true` (default) so the cadence follows the measurement |
| Need reproducible, ungated numbers | `PPE_ADAPTIVE_CADENCE=false` plus `PPE_ROI_REFINE_EVERY_N=1` (what `scripts/validate_detection.py` sets for its run) |

### Known limitations (measured, not guessed)

* **Turnout gear is out of distribution.** The bundled PPE weights were trained on industrial
  workers; firefighters in tan turnout coats score 0.00 on every PPE head, so a fire scene with
  responders will report PPE violations. The supported control is the per-camera profile
  (`set_ppe_profile` / camera configuration): set `required_equipment` to what actually applies to
  that camera's population, or to `[]` for cameras where PPE rules do not apply.
* **No helmet detection by design.** Helmets are removed from the detection stream per requirement.
  The PPE network does detect them (`Hardhat` scored 0.87), so re-enabling is a policy decision, not
  a model change.
* **Clear glasses remain hard.** Glasses are now detected when the head region is resolvable
  (measured 0.25-0.42 on a head crop versus 0.116 full-frame), but a worker 40 m from a 1080p camera
  has ~4 px of eyewear - below what any detector can resolve. Cameras covering PPE-critical areas
  should be positioned or zoomed accordingly.
* **The legacy OpenCV PPE fallbacks remain unreliable and stay off by default.** Measured on the
  sample set, the geometric glasses heuristic reported "goggles 0.95-0.96" on **every** image,
  including firefighters wearing none, and the vest heuristic reported a vest at 0.95 with
  `tape_ratio 0.0` for a plain yellow shirt. They are now gated on real evidence (opaque/tinted
  frame material or facial structure for eyewear; reflective tape or garment structure for a vest),
  which removes those specific fabrications, but they are still heuristics. They only run in mock
  mode or when `ENABLE_CV_GLASSES_FALLBACK_ON_NEURAL_PATH` / `ENABLE_CV_VEST_DETECTION` are
  explicitly enabled.
* **The motion gate is not a replacement for the fire path.** Fire/smoke inference runs on every
  frame regardless of motion, by design: a fire that starts in a still scene must still be seen.

---

## Decoupled Architecture Guarantee

The backend is **completely independent** of frontend frameworks:
- **No HTML/JS rendering**: The backend delivers pure JSON data and standard protocol events.
- **Security Scoping**: Passwords and NVR secrets are strictly contained within backend settings and masked in API outputs.
- **Client Flexibility**: Any client (React, Next.js, Vue, Flutter, iOS, Android, Desktop) can consume the system via REST APIs and WebSockets.
