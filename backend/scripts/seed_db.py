"""
Database Auto-Seeder Script for AI CCTV Fire & Smoke Platform.
Seeds initial database tables with admin user, operator user, sample DVR, and demo RTSP cameras.
"""

import sys
import os

# Ensure working directory is backend folder so .env is loaded correctly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.models.user import User
from app.models.dvr import DVR
from app.models.camera import Camera
from app.utils.security import hash_password
from app.utils.logger import logger


def seed_database():
    """
    Initializes tables and populates seed data if database is empty.
    """
    logger.info("=" * 60)
    logger.info("Database Seeder: Initializing Database Schema & Default Records")
    logger.info("=" * 60)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Admin User
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@aicctv.local",
                hashed_password=hash_password("admin123"),
                full_name="System Administrator",
                role="ADMIN",
                is_active=True,
                is_superuser=True
            )
            db.add(admin)
            logger.info("SeedDB: Created default Admin user ('admin' / 'admin123').")

        # 2. Seed Operator User
        operator = db.query(User).filter(User.username == "operator").first()
        if not operator:
            operator = User(
                username="operator",
                email="operator@aicctv.local",
                hashed_password=hash_password("operator123"),
                full_name="CCTV Monitoring Operator",
                role="OPERATOR",
                is_active=True,
                is_superuser=False
            )
            db.add(operator)
            logger.info("SeedDB: Created default Operator user ('operator' / 'operator123').")

        # 3. Seed Sample DVR
        sample_dvr = db.query(DVR).filter(DVR.name == "HQ Main Entrance DVR").first()
        if not sample_dvr:
            sample_dvr = DVR(
                name="HQ Main Entrance DVR",
                management_host="192.168.1.100",
                management_port=80,
                rtsp_port=554,
                username="admin",
                credential_reference="enc_secret_123",
                manufacturer="HIKVISION",
                channels_count=8,
                status="ONLINE"
            )
            db.add(sample_dvr)
            db.flush()
            logger.info(f"SeedDB: Created sample DVR 'HQ Main Entrance DVR' (ID: {sample_dvr.id}).")

        db.commit()
        logger.info("=" * 60)
        logger.info("SeedDB: Database seeding completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"SeedDB: Exception seeding database: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
