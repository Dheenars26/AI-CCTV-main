"""
MongoDB Service for Alert Event Logging & Queries.
Stores only verified safety alerts with camera context, detection snapshots, and timestamps.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.database.mongodb import mongodb_manager
from app.schemas.mongo_docs import AlertEventQueryFilter
from app.utils.logger import logger


class MongoAlertService:
    """
    Simplified alert-focused MongoDB service.
    Stores one document per verified safety alert (fire, smoke, PPE violation, zone breach).
    """

    @staticmethod
    async def log_alert_event(
        camera_id: int,
        camera_name: str,
        location: Optional[str],
        alert_type: str,
        confidence: float = 0.0,
        snapshot_path: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Persists a single verified alert event into MongoDB 'alert_events'.
        Fails silently if MongoDB is offline to ensure video pipeline is never blocked.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return None

        ts = timestamp or datetime.now(timezone.utc)
        doc = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "location": location,
            "alert_type": alert_type.lower(),
            "confidence": round(float(confidence), 4),
            "snapshot_path": snapshot_path,
            "timestamp": ts,
            "metadata": metadata or {}
        }

        try:
            result = await mongodb_manager.db["alert_events"].insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.debug(f"MongoDB log_alert_event notice (non-fatal): {e}")
            return None

    @staticmethod
    async def query_alert_events(filter_params: AlertEventQueryFilter) -> Dict[str, Any]:
        """
        Queries alert events from MongoDB with filtering and pagination.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return {
                "items": [],
                "total": 0,
                "mongodb_connected": False,
                "message": "MongoDB is offline or unreachable."
            }

        query: Dict[str, Any] = {}

        if filter_params.camera_id is not None:
            query["camera_id"] = filter_params.camera_id

        if filter_params.alert_type:
            query["alert_type"] = filter_params.alert_type.lower()

        time_query = {}
        if filter_params.start_time:
            time_query["$gte"] = filter_params.start_time
        if filter_params.end_time:
            time_query["$lte"] = filter_params.end_time
        if time_query:
            query["timestamp"] = time_query

        try:
            collection = mongodb_manager.db["alert_events"]
            total = await collection.count_documents(query)

            cursor = collection.find(query).sort("timestamp", -1).skip(filter_params.skip).limit(filter_params.limit)
            items = []
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                items.append(doc)

            return {
                "items": items,
                "total": total,
                "limit": filter_params.limit,
                "skip": filter_params.skip,
                "mongodb_connected": True
            }
        except Exception as e:
            logger.error(f"MongoDB query error: {e}")
            return {
                "items": [],
                "total": 0,
                "mongodb_connected": False,
                "error": str(e)
            }

    @staticmethod
    async def get_alerts_by_camera(camera_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent alert events for a specific camera."""
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return []

        try:
            cursor = mongodb_manager.db["alert_events"].find(
                {"camera_id": camera_id}
            ).sort("timestamp", -1).limit(limit)
            items = []
            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                items.append(doc)
            return items
        except Exception as e:
            logger.debug(f"MongoDB get_alerts_by_camera notice: {e}")
            return []


mongo_alert_service = MongoAlertService()


import concurrent.futures

_mongo_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="MongoDispatch")

def schedule_mongo_alert_log(
    camera_id: int,
    camera_name: str,
    location: Optional[str],
    alert_type: str,
    confidence: float = 0.0,
    snapshot_path: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Safely dispatches non-blocking MongoDB alert logging from synchronous worker code.
    Never blocks OpenCV/camera threads and silently catches errors if MongoDB is offline.
    Uses a bounded ThreadPoolExecutor to prevent thread exhaustion during alert storms.
    """
    if not mongodb_manager.is_connected or mongodb_manager.db is None:
        return

    import asyncio

    async def _async_call():
        await mongo_alert_service.log_alert_event(
            camera_id=camera_id,
            camera_name=camera_name,
            location=location,
            alert_type=alert_type,
            confidence=confidence,
            snapshot_path=snapshot_path,
            timestamp=timestamp,
            metadata=metadata
        )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_call())
    except RuntimeError:
        # Submit to the executor instead of spawning an unbounded raw thread
        _mongo_executor.submit(lambda: asyncio.run(_async_call()))
    except Exception as e:
        logger.error(f"MongoDB alert dispatch failed: {e}")
