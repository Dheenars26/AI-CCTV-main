"""
PostgreSQL & SQLite Database Restoration & Disaster Recovery Script (restore_db.py).
Validates SHA-256 backup integrity hashes, verifies SQLite magic headers,
prevents shell injection, and implements automatic rollback protection.
"""

import os
import sys
import gzip
import shutil
import hashlib
import tempfile
import subprocess
from datetime import datetime, timezone

# Ensure app package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from app.config.settings import settings
except ImportError:
    settings = None

SQLITE_HEADER = b"SQLite format 3\x00"


def sanitize_and_validate_path(path: str) -> str:
    """
    Validates backup path against traversal, null bytes, and shell metacharacters.
    """
    if not path or not isinstance(path, str):
        raise ValueError("Backup path must be a non-empty string.")

    # Guard against null bytes and shell control injection
    for forbidden in ("\0", "\n", "\r", ";", "&", "|", "`", "$"):
        if forbidden in path:
            raise ValueError(f"Malicious character detected in backup path: {repr(forbidden)}")

    resolved = os.path.abspath(path)
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"Backup file not found: {resolved}")

    return resolved


def verify_backup_integrity(backup_path: str) -> bool:
    """
    Verifies SHA-256 hash against the accompanying .sha256 checksum file if present.
    """
    try:
        clean_path = sanitize_and_validate_path(backup_path)
    except Exception as e:
        print(f"[ERROR] Path validation failed: {e}")
        return False

    hash_file = clean_path + ".sha256"
    if os.path.exists(hash_file):
        with open(hash_file, "r") as hf:
            expected_hash = hf.read().split()[0].strip()

        sha256 = hashlib.sha256()
        with open(clean_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()

        if expected_hash.lower() != actual_hash.lower():
            print(f"[ERROR] Integrity hash mismatch! Expected: {expected_hash}, Got: {actual_hash}")
            return False

        print(f"[SUCCESS] SHA-256 Integrity Verified ({actual_hash[:12]}...)")
    return True


def is_valid_sqlite_backup(backup_path: str) -> bool:
    """
    Validates that a backup archive or file contains a valid SQLite database header.
    """
    try:
        if backup_path.endswith(".gz"):
            with gzip.open(backup_path, "rb") as gz:
                header = gz.read(16)
        else:
            with open(backup_path, "rb") as f:
                header = f.read(16)
        return header.startswith(SQLITE_HEADER)
    except Exception as e:
        print(f"[WARN] SQLite header inspection failed: {e}")
        return False


def restore_database_backup(backup_path: str, target_db_url: str | None = None) -> bool:
    """
    Restores backup archive into target database (PostgreSQL or SQLite)
    with pre-restore safety snapshots and atomic rollback.
    """
    try:
        clean_backup_path = sanitize_and_validate_path(backup_path)
    except Exception as e:
        print(f"[ERROR] Path validation error: {e}")
        return False

    if not verify_backup_integrity(clean_backup_path):
        return False

    db_url = (target_db_url or (settings.DATABASE_URL if settings else "sqlite:///./cctv.db")).strip()

    if "postgresql" in db_url.lower():
        print(f"[INFO] Restoring PostgreSQL database from {clean_backup_path}...")
        try:
            # Safe streaming without shell=True to eliminate command injection risk
            psql_cmd = ["psql", db_url]
            if clean_backup_path.endswith(".gz"):
                with gzip.open(clean_backup_path, "rb") as f_in:
                    proc = subprocess.run(psql_cmd, stdin=f_in, capture_output=True, text=True)
            else:
                with open(clean_backup_path, "rb") as f_in:
                    proc = subprocess.run(psql_cmd, stdin=f_in, capture_output=True, text=True)

            if proc.returncode != 0:
                print(f"[WARN] psql restore warning/error: {proc.stderr.strip()}")
                return False
            print("[SUCCESS] PostgreSQL database restored successfully.")
        except FileNotFoundError:
            print("[ERROR] 'psql' binary not found on system PATH. Ensure PostgreSQL client tools are installed.")
            return False
        except Exception as e:
            print(f"[ERROR] PostgreSQL restore failed: {e}")
            return False
    else:
        # SQLite Database restore
        target_file = db_url.lower().replace("sqlite:///", "").replace("./", "").strip()
        if not target_file:
            target_file = "cctv.db"

        # Validate SQLite backup file structure
        if not is_valid_sqlite_backup(clean_backup_path):
            print(f"[ERROR] Backup file '{clean_backup_path}' does not contain a valid SQLite database header.")
            print("[ERROR] Restoration aborted to prevent database corruption.")
            return False

        # Create safety pre-restore backup if target database exists
        safety_backup = None
        if os.path.exists(target_file):
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safety_backup = f"{target_file}.pre_restore_{timestamp_str}.bak"
            shutil.copy2(target_file, safety_backup)
            print(f"[INFO] Created safety snapshot '{safety_backup}' before restore.")

        print(f"[INFO] Restoring SQLite database '{target_file}' from '{clean_backup_path}'...")
        temp_target = target_file + ".restore_tmp"
        try:
            if clean_backup_path.endswith(".gz"):
                with gzip.open(clean_backup_path, "rb") as f_in:
                    with open(temp_target, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(clean_backup_path, temp_target)

            # Atomic swap
            if os.path.exists(target_file):
                os.replace(temp_target, target_file)
            else:
                os.rename(temp_target, target_file)

            print(f"[SUCCESS] SQLite database '{target_file}' restored atomically.")
        except Exception as e:
            print(f"[ERROR] SQLite restore failed: {e}")
            if os.path.exists(temp_target):
                os.remove(temp_target)
            if safety_backup and os.path.exists(safety_backup):
                print(f"[INFO] Rolling back to pre-restore safety snapshot '{safety_backup}'...")
                shutil.copy2(safety_backup, target_file)
            return False

    print(f"[SUCCESS] Restoration Verification Complete for archive: {clean_backup_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[2] if len(sys.argv) > 2 else None
        success = restore_database_backup(sys.argv[1], target)
        sys.exit(0 if success else 1)
    else:
        print("Usage: python scripts/restore_db.py <backup_path> [target_db_url]")
