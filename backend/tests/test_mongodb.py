"""
Unit & Integration Tests for MongoDB Hybrid Architecture.
Validates async connection handling, schemas, resilient offline degradation, and mock queries.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.mongodb import MongoDBManager, mongodb_manager, connect_to_mongo, close_mongo_connection, get_mongo_db
from app.schemas.mongo_docs import (
    BoundingBoxDoc,
    DetectionEventDoc,
    CameraTelemetryDoc,
    MongoQueryFilter,
    MongoHealthStatus
)
from app.services.mongo_service import (
    MongoDetectionService,
    mongo_detection_service,
    schedule_mongo_detection_log,
    schedule_mongo_detections_batch
)


@pytest.mark.asyncio
async def test_mongo_schemas_validation():
    """Validates Pydantic schema validation for MongoDB document models."""
    bbox = BoundingBoxDoc(
        x1=10.5,
        y1=20.0,
        x2=100.0,
        y2=200.0,
        confidence=0.88,
        class_name="fire"
    )
    assert bbox.class_name == "fire"
    assert bbox.confidence == 0.88

    event = DetectionEventDoc(
        camera_id=1,
        camera_name="Main Gate Cam",
        detections=[bbox],
        module="FIRE_SMOKE"
    )
    assert event.camera_id == 1
    assert len(event.detections) == 1

    telemetry = CameraTelemetryDoc(
        camera_id=2,
        ai_fps=14.5,
        stream_fps=25.0
    )
    assert telemetry.camera_id == 2
    assert telemetry.ai_fps == 14.5

    query_filter = MongoQueryFilter(camera_id=1, class_name="fire", limit=10)
    assert query_filter.limit == 10
    assert query_filter.class_name == "fire"


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
    """Verifies that MongoDetectionService safely no-ops when MongoDB is offline."""
    # Ensure offline state
    mongodb_manager.is_connected = False
    mongodb_manager.db = None

    # log_detection should return None, not raise
    det_id = await mongo_detection_service.log_detection(
        camera_id=99,
        camera_name="Test Cam",
        class_name="smoke",
        confidence=0.75,
        bounding_box={"x1": 0, "y1": 0, "x2": 50, "y2": 50}
    )
    assert det_id is None

    # log_detections_batch should return 0, not raise
    count = await mongo_detection_service.log_detections_batch(
        camera_id=99,
        camera_name="Test Cam",
        detections=[{"class_name": "fire", "confidence": 0.9}]
    )
    assert count == 0

    # query_detection_history should return empty items with mongodb_connected=False
    res = await mongo_detection_service.query_detection_history(MongoQueryFilter())
    assert res["mongodb_connected"] is False
    assert res["items"] == []


def test_sync_scheduling_helpers():
    """Verifies that synchronous code can call schedule helpers without exceptions."""
    # When offline
    mongodb_manager.is_connected = False
    schedule_mongo_detection_log(
        camera_id=1,
        camera_name="Sync Test Cam",
        class_name="fire",
        confidence=0.85,
        bounding_box={"x1": 10, "y1": 10, "x2": 100, "y2": 100}
    )

    schedule_mongo_detections_batch(
        camera_id=1,
        camera_name="Sync Test Cam",
        detections=[{"class_name": "smoke", "confidence": 0.8}]
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

    # Mock insert_many
    mock_many_res = MagicMock()
    mock_many_res.inserted_ids = ["id_1", "id_2"]
    mock_collection.insert_many = AsyncMock(return_value=mock_many_res)

    # Mock count_documents
    mock_collection.count_documents = AsyncMock(return_value=2)

    # Mock find cursor
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    async def mock_cursor_iter():
        yield {"_id": "id_1", "camera_id": 1, "class_name": "fire", "confidence": 0.91}
        yield {"_id": "id_2", "camera_id": 1, "class_name": "smoke", "confidence": 0.82}

    mock_cursor.__aiter__ = lambda self: mock_cursor_iter()
    mock_collection.find.return_value = mock_cursor

    mock_db.__getitem__.return_value = mock_collection

    with patch.object(mongodb_manager, "is_connected", True):
        with patch.object(mongodb_manager, "db", mock_db):
            # Test log_detection
            doc_id = await mongo_detection_service.log_detection(
                camera_id=1,
                camera_name="Cam 1",
                class_name="fire",
                confidence=0.91,
                bounding_box={"x1": 0, "y1": 0, "x2": 10, "y2": 10}
            )
            assert doc_id == "mock_mongo_id_12345"

            # Test log_detections_batch
            batch_count = await mongo_detection_service.log_detections_batch(
                camera_id=1,
                camera_name="Cam 1",
                detections=[{"class_name": "fire"}, {"class_name": "smoke"}]
            )
            assert batch_count == 2

            # Test query
            history = await mongo_detection_service.query_detection_history(
                MongoQueryFilter(camera_id=1)
            )
            assert history["mongodb_connected"] is True
            assert history["total"] == 2
            assert len(history["items"]) == 2
            assert history["items"][0]["id"] == "id_1"
