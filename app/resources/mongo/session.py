"""Async MongoDB session/connection handling. Thin wrapper over client for lifecycle and health."""

from typing import Any

from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.config.logging import get_logger
from app.resources.mongo.client import get_database, get_mongo_client

logger = get_logger(__name__)


async def ping_mongo() -> dict[str, Any]:
    """
    Ping MongoDB asynchronously. Returns dict with 'ok' bool and optional 'error' string.
    Used for health checks; does not leak internal details.
    """
    try:
        await get_mongo_client().admin.command("ping")
        return {"ok": True}
    except ServerSelectionTimeoutError as e:
        logger.warning("MongoDB ping timeout", extra={"error": str(type(e).__name__)})
        return {"ok": False, "error": "connection_timeout"}
    except PyMongoError as e:
        logger.warning("MongoDB ping failed", extra={"error": str(type(e).__name__)})
        return {"ok": False, "error": "connection_failed"}


def get_mongo_session_db():
    """Return the default database for use as a 'session' target. Same as get_database()."""
    return get_database()
