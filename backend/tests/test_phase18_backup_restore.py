"""
Phase 18 Backup and Restore Verification Tests:
Tests:
1. Creating real database backup via scripts/backup_db.py
2. Verifying SHA-256 integrity file and calculation
3. Altering/corrupting database or state
4. Restoring database via scripts/restore_db.py
5. Verifying database restore recovers original records
"""

import os
import sqlite3
import pytest
from scripts.backup_db import execute_database_backup
from scripts.restore_db import restore_database_backup, verify_backup_integrity


def test_backup_and_restore_cycle(tmp_path):
    """Executes full backup, integrity check, database mutation, and restore cycle."""
    db_file = tmp_path / "test_cctv.db"
    backup_dir = tmp_path / "backups"

    # Step 1: Create initial database with sample data
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT)")
    cur.execute("INSERT INTO users VALUES ('u1', 'admin_original')")
    cur.execute("CREATE TABLE cameras (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("INSERT INTO cameras VALUES (1, 'Front Gate 1')")
    conn.commit()
    conn.close()

    # Step 2: Create Backup
    backup_path = execute_database_backup(output_dir=str(backup_dir), db_url=f"sqlite:///{db_file}")

    assert os.path.exists(backup_path)
    assert os.path.exists(backup_path + ".sha256")
    assert verify_backup_integrity(backup_path) is True

    # Step 3: Mutate database (Simulate disaster or accidental data loss)
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("DELETE FROM users")
    cur.execute("DELETE FROM cameras")
    cur.execute("INSERT INTO users VALUES ('u2', 'hacked_account')")
    conn.commit()
    conn.close()

    # Verify database is currently corrupted
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT username FROM users")
    assert cur.fetchall() == [("hacked_account",)]
    conn.close()

    # Step 4: Execute Restoration
    success = restore_database_backup(backup_path, target_db_url=f"sqlite:///{db_file}")
    assert success is True

    # Step 5: Verify original state is restored
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users")
    users = cur.fetchall()
    assert users == [("u1", "admin_original")]

    cur.execute("SELECT id, name FROM cameras")
    cameras = cur.fetchall()
    assert cameras == [(1, "Front Gate 1")]
    conn.close()
