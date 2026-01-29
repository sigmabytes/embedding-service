"""Async MongoDB client with connection pooling, timeouts, and graceful shutdown using Motor."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from app.config.logging import get_logger
from app.config.storage.mongo import get_mongo_config

logger = get_logger(__name__)

_client: AsyncIOMotorClient | None = None
_default_db: AsyncIOMotorDatabase | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Return the shared async MongoDB client. Creates it on first use."""
    global _client
    if _client is None:
        cfg = get_mongo_config()
        _client = AsyncIOMotorClient(
            cfg["uri"],
            connectTimeoutMS=cfg["connect_timeout_ms"],
            serverSelectionTimeoutMS=cfg["server_selection_timeout_ms"],
            maxPoolSize=cfg["max_pool_size"],
        )
        logger.info(
            "MongoDB async client initialized",
            extra={"database": cfg["database"], "max_pool_size": cfg["max_pool_size"]},
        )
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the default database. Uses shared async client."""
    global _default_db
    if _default_db is None:
        cfg = get_mongo_config()
        _default_db = get_mongo_client()[cfg["database"]]
    return _default_db


def close_mongo_client() -> None:
    """Close the MongoDB client and release connections. Call on app shutdown."""
    global _client, _default_db
    if _client is not None:
        try:
            _client.close()
            logger.info("MongoDB async client closed")
        except Exception as e:
            logger.warning("Error closing MongoDB client", extra={"error": str(e)})
        _client = None
        _default_db = None
