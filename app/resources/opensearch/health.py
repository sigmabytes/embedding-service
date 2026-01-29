"""Async OpenSearch health check. Used by /health or /ready; no business logic."""

from typing import Any

from opensearchpy.exceptions import ConnectionError as OSConnectionError
from opensearchpy.exceptions import ConnectionTimeout as OSConnectionTimeout
from opensearchpy.exceptions import OpenSearchException

from app.config.logging import get_logger
from app.resources.opensearch.client import get_opensearch_client

logger = get_logger(__name__)


async def ping_opensearch() -> dict[str, Any]:
    """
    Ping OpenSearch asynchronously. Returns dict with 'ok' bool and optional 'error' string.
    Used for health checks; does not leak internal details.
    """
    try:
        await get_opensearch_client().ping()
        return {"ok": True}
    except OSConnectionTimeout as e:
        logger.warning("OpenSearch ping timeout", extra={"error": str(type(e).__name__)})
        return {"ok": False, "error": "connection_timeout"}
    except (OSConnectionError, OpenSearchException) as e:
        logger.warning("OpenSearch ping failed", extra={"error": str(type(e).__name__)})
        return {"ok": False, "error": "connection_failed"}
