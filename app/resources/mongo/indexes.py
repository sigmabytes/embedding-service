"""
MongoDB index creation for performance optimization (§3.4).
Creates indexes on frequently queried fields for all collections.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config.logging import get_logger
from app.repositories.mongodb.base import (
    RAW_DOCUMENTS_COLLECTION,
    CHUNKS_COLLECTION,
    EMBEDDINGS_COLLECTION,
)

logger = get_logger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Create all required indexes for optimal query performance.
    Called during application startup.
    """
    try:
        # Raw Documents Collection indexes
        raw_docs = db[RAW_DOCUMENTS_COLLECTION]
        await raw_docs.create_index([("tenant_id", 1)])
        await raw_docs.create_index([("tenant_id", 1), ("document_id", 1)], unique=True)
        await raw_docs.create_index([("status", 1)])
        await raw_docs.create_index([("tenant_id", 1), ("status", 1)])
        logger.info("Created indexes for raw_documents collection")

        # Chunks Collection indexes
        chunks = db[CHUNKS_COLLECTION]
        await chunks.create_index([("tenant_id", 1)])
        await chunks.create_index([("tenant_id", 1), ("document_id", 1)])
        await chunks.create_index([("tenant_id", 1), ("chunk_id", 1)], unique=True)
        await chunks.create_index([("tenant_id", 1), ("document_id", 1), ("chunk_hash", 1)], unique=True)
        await chunks.create_index([("chunk_hash", 1)])
        await chunks.create_index([("status", 1)])
        await chunks.create_index([("tenant_id", 1), ("status", 1)])
        logger.info("Created indexes for chunks collection")

        # Embeddings Collection indexes
        embeddings = db[EMBEDDINGS_COLLECTION]
        await embeddings.create_index([("tenant_id", 1)])
        await embeddings.create_index([("tenant_id", 1), ("chunk_id", 1)])
        await embeddings.create_index([("tenant_id", 1), ("embedding_id", 1)], unique=True)
        await embeddings.create_index(
            [("tenant_id", 1), ("chunk_id", 1), ("embedding_config_hash", 1)], unique=True
        )
        await embeddings.create_index([("embedding_config_hash", 1)])
        await embeddings.create_index([("status", 1)])
        await embeddings.create_index([("tenant_id", 1), ("status", 1)])
        await embeddings.create_index([("tenant_id", 1), ("status", 1), ("embedding_vector", 1)])
        logger.info("Created indexes for embeddings collection")

        logger.info("All MongoDB indexes created successfully")
    except Exception as e:
        logger.error("Failed to create MongoDB indexes", extra={"error": str(e), "error_type": type(e).__name__})
        raise
