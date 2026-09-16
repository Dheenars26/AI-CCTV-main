# Enterprise AI CCTV Fire, Smoke & Workplace Safety Monitoring Platform

An enterprise-grade, frontend-independent AI Monitoring Platform designed to connect to CCTV camera systems through DVR/NVR RTSP video streams.

The backend processes video streams, monitors **Fire, Smoke, PPE Compliance (Helmet, Vest, Mask, Gloves, Goggles, Safety Shoes), Worker Safety Violations, Polygon Hazard Zones, and Unauthorized Area Entries**. It dispatches real-time alerts via WebSockets, Email, and Webhooks, archives evidence snapshots/MP4s, stores detection logs, and exposes standardized REST and WebSocket APIs for any frontend technology.

---

## 🏗️ Architectural Core: Frontend-Independent & Modular

The backend is **100% frontend independent**. Any frontend stack (React, Vue, Next.js, Angular, Flutter, iOS, Android, Desktop, or Python CLI) can consume the platform via REST APIs and WebSocket event channels.

```
                  ┌──────────────────────────────────────────────────┐
                  │          RTSP CCTV / DVR Video Streams           │
                  └────────────────────────┬─────────────────────────┘
                                           │
                                           ▼
                  ┌──────────────────────────────────────────────────┐
                  │    CameraManager & Isolated Frame Pipeline       │
                  └────────────────────────┬─────────────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
│FireSmokeDetector│               │   PPEDetector   │               │ PersonDetector  │
└────────┬────────┘               └────────┬────────┘               └────────┬────────┘
         │                                 │                                 │
         └─────────────────────────────────┼─────────────────────────────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │    PersonTracker    │  (Temporary person_id)
                                └──────────┬──────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │PPEAssociationEngine │  (Body-region spatial rules)
                                └──────────┬──────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │     ZoneEngine      │  (Polygon containment check)
                                └──────────┬──────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │  SafetyRuleEngine   │  (Violation & Incident correlation)
                                └──────────┬──────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │TemporalVerification │  (Finite State Machine)
                                └──────────┬──────────┘
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
│ REST API Gateway│               │ WebSocket Server│               │  Alert Dispatch │
│    (/api/v1)    │               │  (ws://.../ws)  │               │ (Email/Webhook) │
└─────────────────┘               └─────────────────┘               └─────────────────┘
```

---

## Workspace Structure & Frontend Clients

```
AI CCTV/
│
├── backend/                  # Headless Python FastAPI Backend
│   ├── app/                  # Application Source Code
│   │   ├── api/v1/           # REST API Version 1 Endpoints
│   │   ├── camera/           # Multi-Camera Orchestrator & Frame Pipeline
│   │   ├── detection/        # Modular Detectors (BaseDetector, FireSmoke, PPE, Person)
│   │   ├── safety/           # PersonTracker, AssociationEngine, SafetyRuleEngine, Verification
│   │   └── zones/            # ZoneEngine & Polygon Validation
│   └── README.md             # Detailed Backend Documentation
│
├── frontend-react/           # [Frontend 1] React 19 + Vite SOC & Safety Monitoring Dashboard
│   ├── src/                  # React Components, PPE Panels & Zone Drawer
│   └── README.md             # Instructions to run (npm run dev)
│
├── frontend-simple/          # [Frontend 2] Zero-Build Lightweight HTML5/JS Dashboard
│   ├── index.html            # Standalone Single-Page Monitor
│   └── README.md             # Direct launch instructions (open index.html)
│
├── docker-compose.yml        # Containerized PostgreSQL + Backend Stack
└── README.md                 # Project Master Documentation
```

---

## ⚡ Quick Start: Running the Platform

### 1. Start Backend Server (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Swagger REST API Docs**: `http://127.0.0.1:8000/docs`
- **Detector Health Status**: `http://127.0.0.1:8000/api/v1/system/detectors`
- **Prometheus Metrics**: `http://127.0.0.1:8000/metrics`

### 2. Start React Frontend Dashboard

```powershell
cd frontend
npm install
npm run dev
```

📍 **Dashboard URL**: `http://localhost:5173`
- Includes **Live Monitoring**, **PPE Compliance Panel**, **Polygon Safety Zone Drawer**, **Incident Dashboard**, and **Alert History**.

---

## 🛡️ Key Safety Features

1. **Modular Detector Standard (`BaseDetector`)**:
   - Standardized contract: `initialize()`, `detect(frame)`, `get_model_info()`, `health_check()`, `shutdown()`.
   - Implementations: `FireSmokeDetector`, `PPEDetector`, `PersonDetector`, `DummyDetector`.
   - **Safe Startup**: Starts seamlessly in Mock/CPU fallback mode if model weights are missing or CUDA memory is full.

2. **No Facial Biometrics / Privacy Protection**:
   - Tracks workers using temporary, session-scoped `person_id` per camera stream without facial recognition.

3. **Spatial Body Region PPE Rules**:
   - `helmet` ➔ Head region (top 35% of worker bbox)
   - `mask` / `goggles` ➔ Face region (10% - 45% of worker bbox)
   - `vest` ➔ Torso region (18% - 75% of worker bbox)
   - `gloves` ➔ Hands region (45% - 95% of worker bbox)
   - `safety_shoes` ➔ Feet region (65% - 100% of worker bbox)

4. **Polygon Hazard & Restricted Zones**:
   - Validates coordinates (>= 3 points, normalized `[0.0 - 1.0]`).
   - Evaluates point-in-polygon containment via ray-casting.
   - Enforces zone-specific PPE requirement profiles.

5. **Combined Incident Correlation & Cooldown**:
   - Correlates simultaneous hazards (e.g. `FIRE` + `PERSON_IN_HAZARD_ZONE` + `PPE_VIOLATION`) into unified `SAFETY_INCIDENT` alerts with `CRITICAL` severity.
   - Prevents alert spam using per-camera/worker cooldown timers.

6. **Detector Failure Isolation**:
   - Detector exceptions or CUDA OOM errors in one module do not stop other detectors or crash the camera manager.

