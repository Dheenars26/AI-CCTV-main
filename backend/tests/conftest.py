"""
Shared Pytest Fixtures and Test Setup for AI CCTV Monitor.
Uses SQLite in-memory engine with StaticPool for isolated fast test execution.
"""

import os
os.environ["APP_ENV"] = "testing"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config.settings import settings
settings.APP_ENV = "testing"

import app.database.session as session_module

# Configure SQLite in-memory engine with StaticPool for fast test execution
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Patch app.database.session BEFORE importing app.main
session_module.engine = test_engine
session_module.SessionLocal = TestingSessionLocal

from app.main import app
from app.database.base import Base
from app.database.session import get_db


def override_get_db():
    db = TestingSessionLocal()
    try:
        from app.models.camera import Camera
        cam = db.query(Camera).filter(Camera.id == 1).first()
        if not cam:
            cam = Camera(
                id=1,
                name="Test Camera 1",
                camera_number="CAM-01",
                rtsp_url="dummy",
                source_type="dummy",
                location="Test Factory Floor",
                enabled=True,
                fire_smoke_enabled=True,
                ppe_enabled=True,
                person_enabled=True,
                zone_enabled=True
            )
            db.add(cam)
            db.commit()
        yield db
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Creates DB tables once for test session and cleans up resources on shutdown.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    try:
        test_engine.dispose()
    except Exception:
        pass
    if hasattr(app.state, "camera_manager") and app.state.camera_manager:
        try:
            cm = app.state.camera_manager
            for event in list(cm._stop_events.values()):
                event.set()
            cm._threads.clear()
            cm._sources.clear()
            cm._pipelines.clear()
            cm._buffers.clear()
        except Exception:
            pass


@pytest.fixture
def db():
    """
    Yields an isolated SQLAlchemy test database session.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()


@pytest.fixture
def client():
    """
    Provides Starlette TestClient with clean lifespan startup and shutdown per test function.
    """
    with TestClient(app) as test_client:
        yield test_client
    if hasattr(app.state, "camera_manager") and app.state.camera_manager:
        try:
            app.state.camera_manager.stop_all()
        except Exception:
            pass


@pytest.fixture
def admin_user(db):
    """
    Creates and returns an active ADMIN user account for testing.
    """
    from app.models.user import User
    from app.utils.security import hash_password
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        user = User(
            username="admin",
            email="admin@aicctv.local",
            hashed_password=hash_password("admin123"),
            full_name="System Administrator",
            role="ADMIN",
            is_active=True,
            is_superuser=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def auth_headers(admin_user):
    """
    Returns Bearer authorization header dictionary for an authenticated ADMIN user.
    """
    from app.utils.security import create_access_token
    token = create_access_token({"sub": str(admin_user.id), "username": admin_user.username, "role": admin_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def ensure_default_camera(db):
    """
    Ensures a default camera (ID=1) is present in test DB for endpoints requiring valid camera FKs.
    """
    from app.models.camera import Camera
    cam = db.query(Camera).filter(Camera.id == 1).first()
    if not cam:
        cam = Camera(
            id=1,
            name="Test Camera 1",
            camera_number="CAM-01",
            rtsp_url="dummy",
            source_type="dummy",
            location="Test Factory Floor",
            enabled=True,
            fire_smoke_enabled=True,
            ppe_enabled=True,
            person_enabled=True,
            zone_enabled=True
        )
        db.add(cam)
        db.commit()
    return cam


@pytest.fixture(autouse=True)
def clean_db_state():
    """
    Cleans up test entities after each test to maintain DB isolation.
    """
    yield
    try:
        db_session = TestingSessionLocal()
        from app.models.dvr import DVR
        from app.models.camera import Camera
        from app.models.evidence import Evidence
        from app.models.alert import Alert
        from app.models.detection import Detection
        from app.models.incident import Incident
        from app.models.zone import SafetyZone
        from app.models.ppe import PPEProfile, PPEViolation

        db_session.query(Evidence).delete(synchronize_session=False)
        db_session.query(Alert).delete(synchronize_session=False)
        db_session.query(Detection).delete(synchronize_session=False)
        db_session.query(Incident).delete(synchronize_session=False)
        db_session.query(SafetyZone).delete(synchronize_session=False)
        db_session.query(PPEViolation).delete(synchronize_session=False)
        db_session.query(PPEProfile).delete(synchronize_session=False)
        db_session.query(Camera).filter(Camera.id != 1).delete(synchronize_session=False)
        db_session.query(DVR).delete(synchronize_session=False)
        db_session.commit()
        db_session.close()
    except Exception:
        pass


