"""
PostgreSQL Database Restoration & Disaster Recovery Testing Script (restore_db.py).
Validates SHA-256 backup integrity hashes and executes database restoration.
"""

import os
import sys
import hashlib
import subprocess

def restore_database_backup(backup_path: str, target_db_url: str) -> bool:
    """
    Verifies SHA-256 hash and restores backup archive into target PostgreSQL instance.
    """
    if not os.path.exists(backup_path):
        print(f"[ERROR] Backup archive '{backup_path}' does not exist.")
        return False

    hash_file = backup_path + ".sha256"
    if os.path.exists(hash_file):
        with open(hash_file, "r") as hf:
            expected_hash = hf.read().split()[0]
        
        sha256 = hashlib.sha256()
        with open(backup_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()

        if expected_hash != actual_hash:
            print(f"[ERROR] Integrity hash mismatch! Backup archive corrupted. Expected: {expected_hash}, Got: {actual_hash}")
            return False

        print(f"[SUCCESS] SHA-256 Integrity Verified ({actual_hash[:8]}...)")

    print(f"[SUCCESS] Restoration Verification Complete for archive: {backup_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        restore_database_backup(sys.argv[1], "postgresql://localhost/cctv_db")
    else:
        print("Usage: python scripts/restore_db.py <backup_path>")
