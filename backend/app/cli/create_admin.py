"""
CLI Admin Bootstrap Command.
Allows system administrators to create the initial ADMIN user account securely.

Usage:
    python -m app.cli.create_admin --username admin --email admin@aicctv.local --password "SecureAdminPass123!"
"""

import sys
import argparse
from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.models.user import User
from app.utils.security import hash_password
from app.utils.logger import logger


def create_initial_admin(username: str, email: str, password: str, full_name: str = "System Administrator") -> bool:
    """
    Creates initial admin user if not existing.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            existing.hashed_password = hash_password(password)
            existing.failed_login_attempts = 0
            existing.locked_until = None
            existing.is_active = True
            existing.role = "ADMIN"
            db.commit()
            print(f"[SUCCESS] Successfully updated & unlocked existing ADMIN user '{username}' with new Argon2id password.")
            return True

        admin_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role="ADMIN",
            is_active=True,
            is_superuser=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print(f"[SUCCESS] Successfully created initial ADMIN user '{username}' (ID: {admin_user.id}) with Argon2id hash.")
        return True

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to create admin user: {str(e)}")
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create Initial Admin User for AI CCTV Monitor")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--full-name", default="System Administrator", help="Admin full display name")

    args = parser.parse_args()
    create_initial_admin(args.username, args.email, args.password, args.full_name)


if __name__ == "__main__":
    main()
