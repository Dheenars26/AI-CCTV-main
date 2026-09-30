# AI CCTV Workplace Safety & Fire/Smoke Monitoring Platform
## End-to-End Complete Production Deployment Guide

---

## 1. Executive Project & Architecture Overview

This platform is an enterprise-grade AI monitoring system connecting to CCTV/DVR/NVR systems via RTSP video streams. It performs real-time detection of:
- **Fire & Smoke**: Dual-engine ONNX inference and OpenCV physics verification (flicker frequency, roughness, and color temperature).
- **PPE Compliance**: Mandatory detection of Hard Hats (Helmets), High-Visibility Vests, Masks, Gloves, and Safety Shoes with spatial body-region association.
- **Worker Tracking & Restricted Zones**: Ray-casting point-in-polygon containment for hazard zones without facial biometrics.
- **Incident Engine**: Multi-hazard correlation, circular buffer evidence archiving (pre/post-event MP4s and snapshots), and real-time alerts via WebSockets, Email (SMTP), and Webhooks.

### Technology Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, ONNX Runtime, Ultralytics YOLOv8, OpenCV, FFmpeg.
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Lucide Icons, WebSocket client.
- **Data & Telemetry**: PostgreSQL 16 (Relational state & alerts), Redis 7 (Pub/Sub & caching), MongoDB 7.0 (High-frequency telemetry & bounding box series), SQLite (lightweight fallback).
- **Reverse Proxy**: NGINX with TLS 1.3, rate-limiting, and WebSocket connection upgrade.

---

## 2. Hardware & System Prerequisites

| Component | Minimum (1-2 Streams, CPU) | Recommended (4-16 Streams, GPU) |
| :--- | :--- | :--- |
| **CPU** | 4 Cores (Intel i5/Xeon or AMD Ryzen 5) | 8-16 Cores (Intel i7/Xeon or AMD Ryzen 7/9) |
| **RAM** | 8 GB | 16 GB - 32 GB |
| **GPU** | None (CPU inference via ONNX Runtime) | NVIDIA RTX 3060 / 4060 / T4 / A10 (>= 8GB VRAM) |
| **Disk** | 50 GB SSD | 250+ GB NVMe SSD (for video evidence storage) |
| **OS** | Ubuntu 22.04 LTS / Debian 12 / Windows 10/11 | Ubuntu 22.04 LTS (NVIDIA Container Toolkit) |
| **Network** | 100 Mbps LAN | 1 Gbps Gigabit LAN (direct access to camera IP subnet) |

---

## 3. Deployment Method A: Cloud PaaS (Render.com)

Best for cloud demos, client presentations, and off-site testing where hardware servers are not available.

### Step-by-Step Render Deployment:
1. **Push Code to GitHub**:
   Ensure your project is committed to a GitHub repository (private or public).
2. **Sign in to Render**:
   Go to [https://render.com](https://render.com) and log in using your GitHub account.
3. **Deploy with Blueprint**:
   - In Render Dashboard, click **New +** → **Blueprint**.
   - Select your repository and click **Connect**.
   - Render automatically parses `render.yaml` and provisions:
     1. `ai-cctv-backend` (Docker Web Service running FastAPI)
     2. `ai-cctv-frontend` (Static Web Service running React + Vite)
   - Click **Apply**.
4. **Configure Secrets**:
   Under `ai-cctv-backend` Environment Settings, configure:
   - `SECRET_KEY`: Auto-generated or custom 64-char key.
   - `SMTP_USERNAME`, `SMTP_PASSWORD`: For email alerts.
5. **Access**:
   Once builds show **Live**, open the `ai-cctv-frontend` URL (e.g., `https://ai-cctv-frontend.onrender.com`).
   - Default login: `admin` / `admin123`.

---

## 4. Deployment Method B: Production Docker Compose (Recommended)

Best for industrial plants, factories, and commercial sites where cameras reside on a local network (LAN/NVR).

### Step 1: Clone Repository and Check Weights
```bash
git clone <your-repo-url>
cd AI-CCTV-main
```
Verify detection weights in `backend/models/`:
- `fire_smoke.onnx`
- `ppe.onnx`
- `yolov8s.onnx`

### Step 2: Configure Environment Settings
Open `backend/.env.production` and verify settings:
```ini
APP_ENV=production
DEBUG=false
SECRET_KEY=generate_a_random_64_character_hex_secret
DATABASE_URL=postgresql://cctv_user:cctv_secure_pass_2026@postgres:5432/cctv_monitor
REDIS_URL=redis://:cctv_redis_pass_2026@redis:6379/0
MONGO_URI=mongodb://mongo:27017
YOLO_DEVICE=cpu   # Use "0" if NVIDIA GPU is present
ALLOWED_ORIGINS=["*"]
```

### Step 3: Launch Docker Services
```bash
# Build and start all 6 services in detached mode
docker compose up -d --build
```

### Step 4: Verify Services Status
```bash
docker compose ps
```
All services (`cctv_nginx`, `cctv_frontend`, `cctv_backend_api`, `cctv_postgres`, `cctv_redis`, `cctv_mongo`) will show **Up / Healthy**.

### Step 5: Access the Dashboard
- URL: `http://<SERVER_IP_OR_LOCALHOST>`
- Username: `admin`
- Password: `admin123`

---

## 5. Deployment Method C: Direct Bare-Metal / Local Server

For development, testing, or running directly on a Windows/Linux host without Docker.

### 1. Backend Server Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python scripts/seed_db.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/healthz`

### 2. Frontend Dashboard Setup
```bash
cd frontend
npm install
npm run build

# To test development server:
npm run dev
# To serve production bundle:
npx serve -s dist -l 5173
```
- Web Dashboard: `http://localhost:5173`

---

## 6. Post-Deployment Configuration & First-Run Setup

### 1. Immediate Administrator Security
Log in to the dashboard → Go to **Profile / Security** → Update the default password from `admin123` to a secure enterprise password.

### 2. Register CCTV Streams
Navigate to **Cameras** → **Add Camera**:
- **Name**: e.g., "Factory Floor West"
- **Stream Source**:
  - For RTSP IP Camera/DVR: `rtsp://admin:password@192.168.1.120:554/h264Preview_01_main`
  - For Synthetic Demo: Select `synthetic` test mode.
- **Enable Detection Modules**: Check **Fire & Smoke**, **PPE Compliance**, and **Person Tracking**.

### 3. Draw Polygon Safety Zones
1. Open the camera in **Zone Drawer**.
2. Click points on the live canvas to outline restricted areas or machinery perimeters.
3. Choose the rule profile: Mandatory Helmet, High-Vis Vest, Mask, or No-Entry Zone.

### 4. Configure Notification Channels
- In `backend/.env.production` or Dashboard Settings, configure SMTP credentials and alert recipient emails (`dheenacsgroup@gmail.com`).

---

## 7. Troubleshooting & Operational Runbook

| Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **Nginx shows 502 Bad Gateway** | Backend API is still initializing models | Wait 30 seconds for ONNX weights to load, or check `docker compose logs -f backend-api`. |
| **RTSP Stream disconnected** | Camera IP changed or network packet drop | Verify RTSP URL in VLC Media Player; ensure camera firewall permits port 554 RTSP traffic. |
| **CUDA out of memory error** | GPU VRAM saturated | In `backend/.env.production`, switch `YOLO_DEVICE="cpu"` or reduce `MAX_CONCURRENT_AI_JOBS=2`. |
| **WebSocket disconnects frequently** | Proxy timeout setting | Ensure `proxy_read_timeout 86400s;` is set in `nginx.conf`. |
| **Evidence disk full warning** | High frame rate archival | In `.env.production`, set `EVIDENCE_RETENTION_DAYS=7` to auto-purge older snapshots. |

---

## 8. Service Management & Maintenance Commands

```bash
# Check service status
docker compose ps

# View live backend logs
docker compose logs -f backend-api

# Restart entire surveillance platform
docker compose restart

# Stop all services safely
docker compose down

# Backup PostgreSQL Database
docker exec -t cctv_postgres pg_dump -U cctv_user cctv_monitor > backup_$(date +%Y%m%d).sql
```
