"""
Unit & Integration Tests for MongoDB Alert Events Architecture.
Validates async connection handling, schemas, resilient offline degradation, and mock queries.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.mongodb import MongoDBManager, mongodb_manager, connect_to_mongo, close_mongo_connection, get_mongo_db
from app.schemas.mongo_docs import (
    AlertEventDoc,
    AlertEventQueryFilter,
    MongoHealthStatus
)
from app.services.mongo_service import (
    MongoAlertService,
    mongo_alert_service,
    schedule_mongo_alert_log
)


@pytest.mark.asyncio
async def test_mongo_schemas_validation():
    """Validates Pydantic schema validation for MongoDB document models."""
    alert_event = AlertEventDoc(
        camera_id=1,
        camera_name="Main Gate Cam",
        location="Building A - Entrance",
        alert_type="fire",
        confidence=0.88,
        snapshot_path="evidence/2026-09-25/cam1_fire_001.jpg"
    )
    assert alert_event.camera_id == 1
    assert alert_event.alert_type == "fire"
    assert alert_event.location == "Building A - Entrance"
    assert alert_event.snapshot_path == "evidence/2026-09-25/cam1_fire_001.jpg"

    query_filter = AlertEventQueryFilter(camera_id=1, alert_type="fire", limit=10)
    assert query_filter.limit == 10
    assert query_filter.alert_type == "fire"


@pytest.mark.asyncio
async def test_mongo_offline_graceful_handling():
    """Verifies that an offline or invalid MongoDB URL degrades gracefully without crashing."""
    manager = MongoDBManager()
    with patch("app.config.settings.settings.MONGODB_URL", "mongodb://127.0.0.1:59999"):
        with patch("app.config.settings.settings.MONGODB_SERVER_TIMEOUT_MS", 200):
            connected = await manager.connect()
            assert connected is False
            assert manager.is_connected is False

            health = await manager.health_check()
            assert health["connected"] is False
            assert "error" in health


@pytest.mark.asyncio
async def test_mongo_service_when_offline():
    """Verifies that MongoAlertService safely no-ops when MongoDB is offline."""
    # Ensure offline state
    mongodb_manager.is_connected = False
    mongodb_manager.db = None

    # log_alert_event should return None, not raise
    alert_id = await mongo_alert_service.log_alert_event(
        camera_id=99,
        camera_name="Test Cam",
        location="Test Location",
        alert_type="smoke",
        confidence=0.75,
        snapshot_path="evidence/test/snap.jpg"
    )
    assert alert_id is None

    # query_alert_events should return empty items with mongodb_connected=False
    res = await mongo_alert_service.query_alert_events(AlertEventQueryFilter())
    assert res["mongodb_connected"] is False
    assert res["items"] == []


def test_sync_scheduling_helpers():
    """Verifies that synchronous code can call schedule helpers without exceptions."""
    # When offline
    mongodb_manager.is_connected = False
    schedule_mongo_alert_log(
        camera_id=1,
        camera_name="Sync Test Cam",
        location="Test Site",
        alert_type="fire",
        confidence=0.85,
        snapshot_path="evidence/test/fire.jpg"
    )


@pytest.mark.asyncio
async def test_mocked_mongo_insert_and_query():
    """Tests insert and query logic with a mocked Motor database."""
    mock_db = MagicMock()
    mock_collection = MagicMock()

    # Mock insert_one
    mock_result = MagicMock()
    mock_result.inserted_id = "mock_mongo_id_12345"
    mock_collection.insert_one = AsyncMock(return_value=mock_result)

    # Mock count_documents
    mock_collection.count_documents = AsyncMock(return_value=2)

    # Mock find cursor
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    async def mock_cursor_iter():
        yield {
            "_id": "id_1", "camera_id": 1, "camera_name": "Cam 1",
            "location": "Gate A", "alert_type": "fire", "confidence": 0.91,
            "snapshot_path": "evidence/2026-09-25/fire_001.jpg",
            "timestamp": datetime.now(timezone.utc)
        }
        yield {
            "_id": "id_2", "camera_id": 1, "camera_name": "Cam 1",
            "location": "Gate A", "alert_type": "smoke", "confidence": 0.82,
            "snapshot_path": "evidence/2026-09-25/smoke_001.jpg",
            "timestamp": datetime.now(timezone.utc)
        }

    mock_cursor.__aiter__ = lambda self: mock_cursor_iter()
    mock_collection.find.return_value = mock_cursor

    mock_db.__getitem__.return_value = mock_collection

    with patch.object(mongodb_manager, "is_connected", True):
        with patch.object(mongodb_manager, "db", mock_db):
            # Test log_alert_event
            doc_id = await mongo_alert_service.log_alert_event(
                camera_id=1,
                camera_name="Cam 1",
                location="Gate A",
                alert_type="fire",
                confidence=0.91,
                snapshot_path="evidence/2026-09-25/fire_001.jpg"
            )
            assert doc_id == "mock_mongo_id_12345"

            # Test query
            history = await mongo_alert_service.query_alert_events(
                AlertEventQueryFilter(camera_id=1)
            )
            assert history["mongodb_connected"] is True
            assert history["total"] == 2
            assert len(history["items"]) == 2
            assert history["items"][0]["id"] == "id_1"
            assert history["items"][0]["alert_type"] == "fire"
            assert history["items"][0]["snapshot_path"] == "evidence/2026-09-25/fire_001.jpg"
