"""Shared async MongoDB access patterns, tenant/document filters, and common error handling."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from app.config.logging import get_logger
from app.resources.mongo.client import get_database

logger = get_logger(__name__)

# Collection names per §3.1
RAW_DOCUMENTS_COLLECTION = "raw_documents"
CHUNKS_COLLECTION = "chunks"
EMBEDDINGS_COLLECTION = "embeddings"


class RepositoryError(Exception):
    """Raised when a repository operation fails after handling PyMongo errors."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


def _translate_pymongo_error(e: PyMongoError, context: str) -> RepositoryError:
    """Wrap PyMongo errors into a non-leaking RepositoryError."""
    logger.warning(
        "MongoDB operation failed",
        extra={"context": context, "error_type": type(e).__name__},
    )
    return RepositoryError(f"Dependency temporarily unavailable: {context}", cause=e)


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Return the named collection from the default database."""
    db = get_database()
    return db[name]


def raw_documents_collection() -> AsyncIOMotorCollection:
    """Collection for raw documents (§3.1.1)."""
    return get_collection(RAW_DOCUMENTS_COLLECTION)


def chunks_collection() -> AsyncIOMotorCollection:
    """Collection for chunks (§3.1.2)."""
    return get_collection(CHUNKS_COLLECTION)


def embeddings_collection() -> AsyncIOMotorCollection:
    """Collection for embeddings (§3.1.3). Used in Phase 3."""
    return get_collection(EMBEDDINGS_COLLECTION)


def tenant_document_filter(tenant_id: str, document_id: str) -> dict[str, Any]:
    """Filter dict for tenant_id + document_id. Use in queries."""
    return {"tenant_id": tenant_id, "document_id": document_id}


def tenant_filter(tenant_id: str) -> dict[str, Any]:
    """Filter dict for tenant_id only."""
    return {"tenant_id": tenant_id}
