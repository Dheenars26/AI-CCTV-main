"""
Main FastAPI Application Entry Point.
AI CCTV Fire & Smoke Monitoring Platform Backend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.utils.logger import logger
from app.utils.exceptions import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.api.v1.router import api_v1_router
from app.websocket.router import ws_router
from app.websocket.connection_manager import manager as ws_manager
from app.camera.manager import CameraManager
from app.database.session import SessionLocal, get_db
from app.models.camera import Camera
from app.models.user import User
from app.utils.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager handling startup and shutdown events.
    Initializes CameraManager, loads enabled cameras from DB, and manages graceful cleanup.
    """
    logger.info("=" * 60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.APP_ENV} | Debug: {settings.DEBUG}")
    logger.info(f"Configured CORS Origins: {settings.CORS_ORIGINS}")
    logger.info("=" * 60)

    # Register running event loop with WebSocket Connection Manager for worker thread broadcasts
    import asyncio
    try:
        ws_manager.set_loop(asyncio.get_running_loop())
    except Exception:
        pass

    # Instantiate CameraManager per application lifespan
    camera_manager = CameraManager(
        event_callback=lambda event_type, payload: ws_manager.broadcast_event_sync(event_type, payload)
    )
    app.state.camera_manager = camera_manager

    # Auto-load enabled cameras from database if available
    db = SessionLocal()
    try:
        import app.models
        from app.database.base import Base
        from app.database.session import engine
        from sqlalchemy import text
        Base.metadata.create_all(bind=engine)
        db.commit()

        # Auto-migrate missing columns for SQLite & PostgreSQL
        try:
            with engine.connect() as conn:
                is_sqlite = "sqlite" in str(engine.url)
                if is_sqlite:
                    cam_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(cameras)")).fetchall()]
                    if cam_cols:
                        c_definitions = [
                            ("dvr_id", "INTEGER"),
                            ("dvr_channel", "INTEGER"),
                            ("channel_name", "VARCHAR(100)"),
                            ("dvr_address", "VARCHAR(100)"),
                            ("latitude", "FLOAT DEFAULT 13.0827"),
                            ("longitude", "FLOAT DEFAULT 80.2707"),
                            ("fire_smoke_enabled", "BOOLEAN DEFAULT 1"),
                            ("ppe_enabled", "BOOLEAN DEFAULT 1"),
                            ("person_enabled", "BOOLEAN DEFAULT 1"),
                            ("zone_enabled", "BOOLEAN DEFAULT 1"),
                            ("ppe_inference_interval_sec", "FLOAT DEFAULT 0.05"),
                            ("priority", "VARCHAR(20) DEFAULT 'HIGH'"),
                            ("capture_fps", "INTEGER DEFAULT 25"),
                            ("target_ai_fps", "INTEGER DEFAULT 15"),
                            ("frame_skip", "INTEGER DEFAULT 1"),
                            ("gpu_device_id", "INTEGER DEFAULT 0"),
                            ("fps_limit", "INTEGER DEFAULT 25"),
                            ("connection_timeout", "INTEGER DEFAULT 10"),
                            ("reconnect_interval", "INTEGER DEFAULT 5")
                        ]
                        for c_name, c_type in c_definitions:
                            if c_name not in cam_cols:
                                try:
                                    conn.execute(text(f"ALTER TABLE cameras ADD COLUMN {c_name} {c_type}"))
                                    conn.commit()
                                    logger.info(f"App Lifespan: Auto-added missing column '{c_name}' to cameras table.")
                                except Exception as e:
                                    logger.warning(f"App Lifespan: Could not add column '{c_name}' to cameras: {e}")

                    det_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(detections)")).fetchall()]
                    if det_cols and "module" not in det_cols:
                        conn.execute(text("ALTER TABLE detections ADD COLUMN module VARCHAR(50) DEFAULT 'FIRE_SMOKE'"))
                        conn.commit()

                    alt_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(alerts)")).fetchall()]
                    if alt_cols:
                        if "module" not in alt_cols:
                            conn.execute(text("ALTER TABLE alerts ADD COLUMN module VARCHAR(50) DEFAULT 'FIRE_SMOKE'"))
                            conn.commit()
                        if "remedial_action" not in alt_cols:
                            conn.execute(text("ALTER TABLE alerts ADD COLUMN remedial_action VARCHAR(100)"))
                            conn.commit()
                        if "remedy_notes" not in alt_cols:
                            conn.execute(text("ALTER TABLE alerts ADD COLUMN remedy_notes VARCHAR(500)"))
                            conn.commit()
                        if "resolved_by" not in alt_cols:
                            conn.execute(text("ALTER TABLE alerts ADD COLUMN resolved_by VARCHAR(100)"))
                            conn.commit()
                else:
                    # PostgreSQL IF NOT EXISTS column migrations
                    postgres_stmts = [
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS dvr_id INTEGER",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS dvr_channel INTEGER",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS channel_name VARCHAR(100)",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS dvr_address VARCHAR(100)",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS latitude FLOAT DEFAULT 13.0827",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS longitude FLOAT DEFAULT 80.2707",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS fire_smoke_enabled BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ppe_enabled BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS person_enabled BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS zone_enabled BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ppe_inference_interval_sec FLOAT DEFAULT 0.05",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'HIGH'",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS capture_fps INTEGER DEFAULT 25",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS target_ai_fps INTEGER DEFAULT 15",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS frame_skip INTEGER DEFAULT 1",
                        "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS gpu_device_id INTEGER DEFAULT 0",
                        "ALTER TABLE detections ADD COLUMN IF NOT EXISTS module VARCHAR(50) DEFAULT 'FIRE_SMOKE'",
                        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS module VARCHAR(50) DEFAULT 'FIRE_SMOKE'",
                        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS remedial_action VARCHAR(100)",
                        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS remedy_notes VARCHAR(500)",
                        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(100)"
                    ]
                    for stmt in postgres_stmts:
                        try:
                            conn.execute(text(stmt))
                            conn.commit()
                        except Exception:
                            pass
        except Exception as mig_err:
            logger.warning(f"App Lifespan: DB column migration check warning: {str(mig_err)}")
        # Auto-migrate any lowercase user roles to uppercase in DB
        try:
            with engine.connect() as conn:
                conn.execute(text("UPDATE users SET role = UPPER(role) WHERE role != UPPER(role)"))
                conn.commit()
        except Exception:
            pass

        # Auto-seed default Admin User if database is empty
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@aicctv.local",
                hashed_password=hash_password("admin123"),
                full_name="System Administrator",
                role="ADMIN",
                is_active=True,
                is_superuser=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("App Lifespan: Auto-created default Admin user ('admin' / 'admin123').")

        all_cameras = db.query(Camera).all()
        logger.info(f"App Lifespan: Loaded {len(all_cameras)} camera(s) into CameraManager.")
        for cam in all_cameras:
            camera_manager.add_camera(cam)
            if cam.enabled and getattr(settings, "APP_ENV", "development") != "testing":
                camera_manager.start_camera(cam.id)
        
        # Auto-purge expired evidence & sync disk evidence in background (non-blocking, skip during pytest)
        if settings.APP_ENV != "testing":
            import threading as _threading
            def _bg_evidence_sync():
                try:
                    from app.database.session import SessionLocal as _SL
                    from app.recording.evidence_service import EvidenceService
                    _db = _SL()
                    try:
                        ev_svc = EvidenceService()
                        ev_svc.purge_expired_evidence(retention_days=1, db=_db)
                        ev_svc.sync_disk_evidence_to_db(_db)
                    finally:
                        _db.close()
                except Exception as e:
                    logger.warning(f"App Lifespan: Background evidence sync warning: {str(e)}")
            _threading.Thread(target=_bg_evidence_sync, daemon=True, name="EvidenceSyncWorker").start()

        logger.info("App Lifespan: Cameras started. Evidence sync running in background.")

    except Exception as e:
        logger.warning(f"App Lifespan: Could not auto-load cameras from DB on startup (Tables might not be initialized yet): {str(e)}")
    finally:
        db.expunge_all()
        db.close()

    yield

    # Shutdown tasks
    logger.info("Shutting down AI CCTV Monitor Application backend gracefully...")
    if hasattr(app, "state") and hasattr(app.state, "camera_manager") and app.state.camera_manager:
        try:
            app.state.camera_manager.stop_all()
        except Exception as err:
            logger.warning(f"App Lifespan Shutdown Exception: {str(err)}")


def create_application() -> FastAPI:
    """
    FastAPI Application Factory.
    Creates and configures the FastAPI application instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description=(
            "Enterprise-grade, frontend-independent AI CCTV Fire & Smoke Monitoring Platform Backend. "
            "Exposes REST APIs and WebSockets for camera management, real-time alert notifications, "
            "and event querying across web, mobile, and desktop clients."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # 1. Custom Request ID Middleware
    app.add_middleware(RequestIDMiddleware)

    # 2. Security Headers Middleware (Dynamic HSTS & modern security headers)
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Rate Limiting Middleware (Separate Login vs API limits)
    app.add_middleware(RateLimitMiddleware)

    # 4. Configurable Universal CORS Middleware (Supports ANY frontend framework, origin, or port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else [],
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-CSRF-Token", "Content-Disposition"]
    )

    # 3. Global Exception Handlers
    register_exception_handlers(app)

    # 4. Mount Static Files Directory for Direct Evidence Access (/evidence)
    import os
    from fastapi.staticfiles import StaticFiles
    os.makedirs(settings.EVIDENCE_STORAGE_DIR, exist_ok=True)
    app.mount("/evidence", StaticFiles(directory=settings.EVIDENCE_STORAGE_DIR), name="evidence")

    # 5. Include Routers
    # Versioned REST APIs (/api/v1/...)
    app.include_router(api_v1_router)

    # WebSockets (/ws/v1/...)
    app.include_router(ws_router)

    # Root URL Redirect to Swagger Documentation
    @app.get("/", summary="Root Documentation Redirect", include_in_schema=False)
    def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")

    # Top-level Health Check Endpoint (/health & /healthz for Render/Docker)
    @app.get("/healthz", summary="Lightweight Liveness Probe", tags=["Health"])
    def healthz():
        return {"status": "ok", "service": "ai-cctv-monitor"}

    @app.get("/health", summary="Top-Level Subsystem Health Status", tags=["Health"])
    def root_health_check(request: Request, db: Session = Depends(get_db)):
        from app.api.v1.endpoints.system import comprehensive_health_status
        return comprehensive_health_status(request, db)

    # 6. OpenAPI Custom Security Scheme (Renders green 'Authorize 🔓' button in Swagger UI)
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi
        openapi_schema = get_openapi(
            title=settings.APP_NAME,
            version=settings.VERSION,
            description=app.description,
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "OAuth2PasswordBearer": {
                "type": "oauth2",
                "flows": {
                    "password": {
                        "tokenUrl": "/api/v1/auth/token",
                        "scopes": {}
                    }
                }
            },
            "HTTPBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter JWT Bearer token obtained from POST /api/v1/auth/login"
            }
        }
        openapi_schema["security"] = [{"OAuth2PasswordBearer": []}, {"HTTPBearer": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app



app = create_application()
