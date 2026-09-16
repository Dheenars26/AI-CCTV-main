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

## Decoupled Architecture Guarantee

The backend is **completely independent** of frontend frameworks:
- **No HTML/JS rendering**: The backend delivers pure JSON data and standard protocol events.
- **Security Scoping**: Passwords and NVR secrets are strictly contained within backend settings and masked in API outputs.
- **Client Flexibility**: Any client (React, Next.js, Vue, Flutter, iOS, Android, Desktop) can consume the system via REST APIs and WebSockets.
