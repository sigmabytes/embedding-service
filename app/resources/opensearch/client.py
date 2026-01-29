"""Async OpenSearch client with connection pooling, timeouts, and graceful shutdown."""

from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import OpenSearchException

from app.config.logging import get_logger
from app.config.storage.opensearch import get_opensearch_config

logger = get_logger(__name__)

_client: AsyncOpenSearch | None = None


def get_opensearch_client() -> AsyncOpenSearch:
    """Return the shared async OpenSearch client. Creates it on first use."""
    global _client
    if _client is None:
        cfg = get_opensearch_config()
        _client = AsyncOpenSearch(
            hosts=[cfg["host"]],
            http_auth=(cfg["username"], cfg["password"]),
            use_ssl=cfg["use_ssl"],
            verify_certs=cfg["verify_certs"],
            timeout=cfg["timeout"],
        )
        logger.info(
            "OpenSearch async client initialized",
            extra={"host": cfg["host"], "timeout": cfg["timeout"]},
        )
    return _client


def close_opensearch_client() -> None:
    """Close the OpenSearch client and release connections. Call on app shutdown."""
    global _client
    if _client is not None:
        try:
            _client.close()
            logger.info("OpenSearch async client closed")
        except Exception as e:
            logger.warning("Error closing OpenSearch client", extra={"error": str(e)})
        _client = None
