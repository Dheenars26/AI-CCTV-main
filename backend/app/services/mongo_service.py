"""
MongoDB Service for Detection Event Ingestion & Telemetry Queries.
Provides non-blocking async writes and indexed time-range queries.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.database.mongodb import mongodb_manager
from app.schemas.mongo_docs import DetectionEventDoc, BoundingBoxDoc, CameraTelemetryDoc, MongoQueryFilter
from app.utils.logger import logger


class MongoDetectionService:
    """
    High-throughput ingestion and query service for MongoDB detection and telemetry records.
    """

    @staticmethod
    async def log_detection(
        camera_id: int,
        camera_name: str,
        class_name: str,
        confidence: float,
        bounding_box: Dict[str, Any],
        frame_number: int = 0,
        fps: float = 0.0,
        module: str = "GENERAL",
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Persists a single frame detection event into MongoDB 'detection_logs'.
        Fails silently if MongoDB is offline to ensure video pipeline is never blocked.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return None

        ts = timestamp or datetime.now(timezone.utc)
        doc = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "class_name": class_name.lower(),
            "confidence": round(float(confidence), 4),
            "bounding_box": bounding_box,
            "frame_number": frame_number,
            "fps": round(float(fps), 2),
            "module": module.upper(),
            "timestamp": ts,
            "metadata": metadata or {}
        }

        try:
            result = await mongodb_manager.db["detection_logs"].insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.debug(f"MongoDB log_detection notice (non-fatal): {e}")
            return None

    @staticmethod
    async def log_detections_batch(
        camera_id: int,
        camera_name: str,
        detections: List[Dict[str, Any]],
        frame_number: int = 0,
        fps: float = 0.0,
        module: str = "GENERAL",
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Persists a batch of detections from an inference frame in a single bulk insert.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None or not detections:
            return 0

        ts = timestamp or datetime.now(timezone.utc)
        docs = []
        for det in detections:
            docs.append({
                "camera_id": camera_id,
                "camera_name": camera_name,
                "class_name": det.get("class_name", "unknown").lower(),
                "confidence": round(float(det.get("confidence", 0.0)), 4),
                "bounding_box": det.get("bounding_box", {}),
                "track_id": det.get("track_id"),
                "frame_number": frame_number,
                "fps": round(float(fps), 2),
                "module": module.upper(),
                "timestamp": ts,
                "metadata": metadata or {}
            })

        try:
            result = await mongodb_manager.db["detection_logs"].insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            logger.debug(f"MongoDB log_detections_batch notice (non-fatal): {e}")
            return 0

    @staticmethod
    async def log_telemetry(
        camera_id: int,
        camera_name: str,
        ai_fps: float,
        stream_fps: float,
        active_worker_tracks: int = 0,
        active_violations: int = 0,
        inference_latency_ms: float = 0.0
    ) -> Optional[str]:
        """
        Persists stream processing and hardware performance telemetry.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return None

        doc = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "timestamp": datetime.now(timezone.utc),
            "ai_fps": round(float(ai_fps), 2),
            "stream_fps": round(float(stream_fps), 2),
            "inference_latency_ms": round(float(inference_latency_ms), 2),
            "active_worker_tracks": active_worker_tracks,
            "active_violations": active_violations
        }

        try:
            res = await mongodb_manager.db["telemetry_logs"].insert_one(doc)
            return str(res.inserted_id)
        except Exception as e:
            logger.debug(f"MongoDB log_telemetry notice: {e}")
            return None

    @staticmethod
    async def query_detection_history(filter_params: MongoQueryFilter) -> Dict[str, Any]:
        """
        Queries indexed detection logs from MongoDB with filtering and pagination.
        """
        if not mongodb_manager.is_connected or mongodb_manager.db is None:
            return {
                "items": [],
                "total": 0,
                "mongodb_connected": False,
                "message": "MongoDB is offline or unreachable. Detection logs are running in graceful fallback."
            }

        query: Dict[str, Any] = {}

        if filter_params.camera_id is not None:
            query["camera_id"] = filter_params.camera_id

        if filter_params.class_name:
            query["class_name"] = filter_params.class_name.lower()

        if filter_params.module:
            query["module"] = filter_params.module.upper()

        time_query = {}
        if filter_params.start_time:
            time_query["$gte"] = filter_params.start_time
        if filter_params.end_time:
            time_query["$lte"] = filter_params.end_time
        if time_query:
            query["timestamp"] = time_query

        try:
            collection = mongodb_manager.db["detection_logs"]
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


mongo_detection_service = MongoDetectionService()


def schedule_mongo_detection_log(
    camera_id: int,
    camera_name: str,
    class_name: str,
    confidence: float,
    bounding_box: Dict[str, Any],
    frame_number: int = 0,
    fps: float = 0.0,
    module: str = "GENERAL",
    timestamp: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Safely dispatches non-blocking MongoDB detection logging from synchronous worker code.
    Never blocks OpenCV/camera threads and silently catches errors if MongoDB is offline.
    """
    if not mongodb_manager.is_connected or mongodb_manager.db is None:
        return

    import asyncio
    import threading

    async def _async_call():
        await mongo_detection_service.log_detection(
            camera_id=camera_id,
            camera_name=camera_name,
            class_name=class_name,
            confidence=confidence,
            bounding_box=bounding_box,
            frame_number=frame_number,
            fps=fps,
            module=module,
            timestamp=timestamp,
            metadata=metadata
        )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_call())
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(_async_call()), daemon=True).start()
    except Exception as e:
        logger.debug(f"MongoDB dispatch notice: {e}")


def schedule_mongo_detections_batch(
    camera_id: int,
    camera_name: str,
    detections: List[Dict[str, Any]],
    frame_number: int = 0,
    fps: float = 0.0,
    module: str = "GENERAL",
    timestamp: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Safely dispatches batch of detection documents to MongoDB from synchronous code.
    """
    if not mongodb_manager.is_connected or mongodb_manager.db is None or not detections:
        return

    import asyncio
    import threading

    async def _async_call():
        await mongo_detection_service.log_detections_batch(
            camera_id=camera_id,
            camera_name=camera_name,
            detections=detections,
            frame_number=frame_number,
            fps=fps,
            module=module,
            timestamp=timestamp,
            metadata=metadata
        )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_call())
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(_async_call()), daemon=True).start()
    except Exception as e:
        logger.debug(f"MongoDB batch dispatch notice: {e}")
