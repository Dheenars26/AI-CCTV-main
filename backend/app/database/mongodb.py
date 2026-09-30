"""
MongoDB Async Database Manager (Motor / PyMongo).
Provides resilient, connection-pooled async client access with graceful offline fallback.
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING

from app.config.settings import settings
from app.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Motor is an optional dependency: MongoDB is an add-on telemetry store, and the detection path
# must import cleanly on installations that only run the relational database. Importing it lazily
# also means a missing/broken driver degrades to "MongoDB unavailable" instead of breaking the API.
try:  # pragma: no cover - environment dependent
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    MOTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    AsyncIOMotorClient: Any = None
    AsyncIOMotorDatabase: Any = None
    MOTOR_AVAILABLE = False



class MongoDBManager:
    """
    Singleton Manager for Asynchronous MongoDB connection pooling.
    Handles connection lifecycle, health diagnostics, and graceful degradation.
    """
    client: Optional[Any] = None
    db: Optional[Any] = None
    is_connected: bool = False
    last_error: Optional[str] = None

    async def connect(self) -> bool:
        """
        Establishes non-blocking connection to MongoDB.
        If MongoDB is offline or unreachable, logs a warning and degrades gracefully without throwing.
        """
        if not getattr(settings, "MONGODB_ENABLED", True):
            logger.info("MongoDB is disabled via MONGODB_ENABLED=False setting.")
            self.is_connected = False
            return False

        client_cls = AsyncIOMotorClient
        if not MOTOR_AVAILABLE or client_cls is None:
            self.is_connected = False
            self.last_error = "motor driver not installed"
            logger.warning(
                "MongoDB is enabled but the 'motor' driver is not installed; "
                "detection logging falls back to the relational database only."
            )
            return False

        url = getattr(settings, "MONGODB_URL", "mongodb://localhost:27017")
        db_name = getattr(settings, "MONGODB_DB_NAME", "cctv_ai_surveillance")
        timeout_ms = getattr(settings, "MONGODB_SERVER_TIMEOUT_MS", 2500)

        try:
            logger.info(f"Connecting to MongoDB at '{url}' (database: '{db_name}')...")
            client = client_cls(
                url,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
                maxPoolSize=50,
                minPoolSize=5
            )
            db = client[db_name]
            self.client = client
            self.db = db

            # Fast ping check
            await db.command("ping")
            self.is_connected = True
            self.last_error = None
            logger.info(f"MongoDB connected successfully to database '{db_name}'.")

            # Ensure optimal query indices
            await self._ensure_indices()
            return True

        except Exception as exc:
            self.is_connected = False
            self.last_error = str(exc)
            logger.warning(
                f"MongoDB connection to '{url}' failed or timed out ({exc}). "
                "System running in graceful offline mode for MongoDB telemetry."
            )
            return False

    async def _ensure_indices(self) -> None:
        """Drops legacy collections and creates indices on the new alert_events collection."""
        if not self.is_connected or self.db is None:
            return

        try:
            # Drop legacy collections that stored verbose per-frame data
            existing = await self.db.list_collection_names()
            for legacy_coll in ["detection_logs", "telemetry_logs"]:
                if legacy_coll in existing:
                    await self.db.drop_collection(legacy_coll)
                    logger.info(f"MongoDB: Dropped legacy collection '{legacy_coll}'.")

            # alert_events indices
            await self.db["alert_events"].create_index([("camera_id", 1), ("timestamp", -1)])
            await self.db["alert_events"].create_index([("timestamp", -1)])
            await self.db["alert_events"].create_index([("alert_type", 1)])
            logger.debug("MongoDB: Query indices verified on 'alert_events'.")
        except Exception as e:
            logger.warning(f"MongoDB: Index creation warning: {e}")

    async def close(self) -> None:
        """Closes all MongoDB client connection sockets."""
        if self.client:
            logger.info("Closing MongoDB connection pool...")
            self.client.close()
            self.client = None
            self.db = None
            self.is_connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Returns real-time health and diagnostics of the MongoDB instance."""
        status = {
            "enabled": getattr(settings, "MONGODB_ENABLED", True),
            "connected": self.is_connected,
            "url": getattr(settings, "MONGODB_URL", "mongodb://localhost:27017"),
            "database": getattr(settings, "MONGODB_DB_NAME", "cctv_ai_surveillance"),
            "collections": [],
            "document_counts": {},
            "error": self.last_error
        }

        if self.is_connected and self.db is not None:
            try:
                # Test ping
                await self.db.command("ping")
                collections = await self.db.list_collection_names()
                status["collections"] = collections

                # Count documents in primary collections
                counts = {}
                for coll_name in ["alert_events"]:
                    if coll_name in collections:
                        counts[coll_name] = await self.db[coll_name].count_documents({})
                    else:
                        counts[coll_name] = 0
                status["document_counts"] = counts
            except Exception as exc:
                status["connected"] = False
                status["error"] = str(exc)

        return status


# Global MongoDB Manager Singleton
mongodb_manager = MongoDBManager()


async def connect_to_mongo() -> bool:
    """Helper called by FastAPI lifespan on startup."""
    return await mongodb_manager.connect()


async def close_mongo_connection() -> None:
    """Helper called by FastAPI lifespan on shutdown."""
    await mongodb_manager.close()


def get_mongo_db() -> Optional[Any]:
    """FastAPI dependency for accessing the MongoDB database instance."""
    if mongodb_manager.is_connected:
        return mongodb_manager.db
    return None

